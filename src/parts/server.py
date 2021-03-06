#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Created on Oct 9, 2013

@author: schernikov
'''

import os, uuid, argparse, json, dateparser
import tornado.ioloop, tornado.web, tornado.websocket

import configs.client, configs.server
import parts.misc
import parts.controller
import parts.actions
import parts.area
import parts.sessions

loc = os.path.normpath(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'web')))

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write({"msg":"Hello, world"})

def convert(mod):
    d = {}
    for nm in dir(mod):
        if nm.startswith('_'): continue
        d[nm] = getattr(mod, nm)
    return d


class SocketHandler(tornado.websocket.WebSocketHandler):
    sessions = None

    def open(self):
        self._client_ip = self.request.headers.get('X-Real-IP', None) or self.request.remote_ip
        parts.misc.logger.info("new session from %s"%(self._client_ip))

        msg = self.sessions.onsession(self)
        
        self.sendsession({'init':convert(configs.client)})

        self.write_message(msg)
        
    def on_message(self, message):
        msg = json.loads(message)
        tp = msg.get('type', None)
        if tp == 'session':
            cont = msg.get('cont', None)
            if cont == 'ping':
                self.sendsession('pong')
        elif tp == 'event':
            cont = msg.get('cont', None)
            if cont:
                self.onevent(cont)
        else:
            parts.misc.logger.info("ws: "+message)

    def on_close(self):
        parts.misc.logger.info("closing session from %s"%(self._client_ip))
        self.sessions.offsession(self)
        
    def sendsession(self, msg):
        self.write_message({'type':'session', 'cont':msg})
        
    def onevent(self, msg):
        relay = msg.get('relay', None)
        area = msg.get('area', None)
        state = msg.get('state', None)
        if (relay is None and area is None) or state is None:
            parts.misc.logger.info("unexpected event: %s"%(str(msg)))
            return
        if isinstance(state, basestring): state = state.lower().strip()
        if relay:
            self.sessions.onrelay(relay, state=='on')

        if area:
            self.sessions.onarea(area, state=='on')
                
class JSHandler(tornado.web.StaticFileHandler):

    def get_content_type(self):
        return 'application/javascript; charset=utf-8'


def main():
    def_conf = os.path.normpath(os.path.join(os.path.dirname(__file__), '../configs/config.json'))

    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', help='tornado listen port', required=True, type=int)
    parser.add_argument('-n', '--ping', help='url to ping')
    parser.add_argument('-s', '--host', help='tornado host address (default: %(default)s)', default='localhost')
    parser.add_argument('--config', help='JSON file with pin configuration and area definitions. Default %(default)s', 
                        default=def_conf)
    parser.add_argument('-v', '--verbosity', help='verbosity level', type=int,  
                        choices=[parts.misc.logging.ERROR, 
                                 parts.misc.logging.WARNING, 
                                 parts.misc.logging.INFO, 
                                 parts.misc.logging.DEBUG, 
                                 parts.misc.VERBOSE_LEVEL], default=parts.misc.logging.INFO)
    args = parser.parse_args()

    verb = parts.misc.logging.getLevelName(args.verbosity)
    print "log level", verb
    parts.misc.log_level(getattr(parts.misc.logging, verb, 'INFO'))

    try:
        load_config(configs.server, args.config)
    except Exception, e:
        print str(e)
        return

    conf_start = getattr(configs.server, 'start', None)
    if conf_start:
        start_time = get_time(conf_start)
        if not start_time:
            print "Don't know what to do with '%s' start time"%(conf_start)
            return
    else:
        start_time = None
        
    conf_retry = getattr(configs.server, 'retry', None)
    if not conf_retry:
        print "Config must have 'retry' time value"
        return

    retry = get_time(conf_retry, delta=True)
    if not retry:
        print "Don't know what to do with '%s' retry time"%(conf_retry)
        return

    parts.misc.logger.info('listening on %s:%d'%(args.host, args.port))

    inst = tornado.ioloop.IOLoop.instance()

    action = parts.actions.Action(inst.call_later, args.ping)
    relays = parts.controller.RelayControl()
    area = parts.area.AreaControl()
    try:
        sensor = parts.controller.SensorControl(action)
        sensor
        sessions = parts.sessions.SessionControl(action, relays, area)
    
        SocketHandler.sessions = sessions
    
        app = tornado.web.Application([
                                       (r'/data', MainHandler),
                                       (r'/websocket', SocketHandler),
                                       (r'/(index.html)', tornado.web.StaticFileHandler, {"path": loc}),
                                       (r'/ui/(.*)$', tornado.web.StaticFileHandler, {"path": os.path.join(loc, 'ui')}),
                                       (r'/js/(.*)$', JSHandler, {"path": os.path.join(loc, 'js')}),
                                      ], debug=configs.server.debug, cookie_secret=str(uuid.uuid4()))
        
        app.listen(args.port, address=args.host)
    
        action.schedule(start_time, retry)
    
        periodic = tornado.ioloop.PeriodicCallback(action.check_expired, configs.server.poll_expired_seconds*1000.0)
        periodic.start()
    
        inst.start()
    except KeyboardInterrupt:
        print "Exiting..."
    finally:
        parts.misc.logger.info("Cleaning up")
        parts.controller.cleanup()


def get_time(time_str, delta=False):
    now = dateparser.parse('now', settings={'PREFER_DATES_FROM': 'future', 'RETURN_AS_TIMEZONE_AWARE': True})
    stamp = dateparser.parse(time_str, settings={'PREFER_DATES_FROM': 'future',
                                                      'RETURN_AS_TIMEZONE_AWARE': True,
                                                      'RELATIVE_BASE':now})
    if not stamp: return None

    if stamp < now:
        td = now - stamp
        if delta: return td
        return now + td
    
    if delta: return stamp - now

    return stamp


def load_config(mod, fname):
    if not os.path.isfile(fname):
        raise Exception('%s is not a file'%(fname))

    with open(fname) as f:    
        try:
            conf = json.load(f)
        except Exception, e:
            raise Exception('%s is not valid JSON file: %s'%(fname, str(e)))
    
    for nm, val in conf.items():
        setattr(mod, nm, val)

    
if __name__ == "__main__":
    main()
