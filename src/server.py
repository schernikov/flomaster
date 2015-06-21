#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Created on Oct 9, 2013

@author: schernikov
'''

import os, uuid, argparse, threading, json, datetime, pytz
import tornado.ioloop, tornado.web, tornado.websocket
import misc, controller, configs.client

loc = os.path.normpath(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'web')))

tz = pytz.timezone('US/Pacific')

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write({"msg":"Hello, world"})

class DevControl(object):
    def __init__(self):
        self.device = None
        self.sockset = set()
        self.lock = threading.RLock()
        
    def onsock(self, sock):
        self.lock.acquire()
        self.sockset.add(sock)
        self.lock.release()
        
    def offsock(self, sock):
        self.lock.acquire()
        self.sockset.discard(sock)
        self.lock.release()
    
    def flow(self, **kargs):
        self.broadcast({'type':'flow', 'cont':kargs})

    def broadcast(self, dd, skip=None):
        self.lock.acquire()
        for sock in self.sockset:
            if sock == skip: continue
            sock.write_message(dd)
        self.lock.release()

class AreaControl(object):

    @classmethod
    def info(cls):
        return [[a[0], a[1]] for a in controller.areas]

    def __init__(self):
        self._active = None
        self._lock = threading.RLock()
        
    def state(self):
        'return currently active index or None'
        return self._active
    
    def set(self, index, active, handler):
        if not active:
            if self._active == index:
                self._active = None
              
                self._onset(handler, (index, False), (controller.master, False))
            return
        
        if self._active is None:
            self._active = index
            
            self._onset(handler, (controller.master, True), (index, True))
            return
        
        self._onset(handler, (self._active, False), (index, True))

        self._active = index

    def _onset(self, handler, args1, args2):
        self._lock.acquire()
        
        handler(*args1)
        handler(*args2)
        
        self._lock.release()


def convert(mod):
    d = {}
    for nm in dir(mod):
        if nm.startswith('_'): continue
        d[nm] = getattr(mod, nm)
    return d

class SocketHandler(tornado.websocket.WebSocketHandler):
    control = DevControl()
    areacon = AreaControl()

    def open(self):
        misc.logger.info("new socket"+str(self))
        self.control.onsock(self)
        self.sendsession({'init':convert(configs.client)})
        dstat = self.control.device.status()
        ainfo = self.areacon.info()
        dstat.update({'areas':ainfo, 'master':controller.master})
        active = self.areacon.state()
        if active: dstat['active'] = active
        self.sendevent({'init':dstat})
        
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
            misc.logger.info("ws: "+message)
        
    def on_close(self):
        misc.logger.info("ws: closed")
        self.control.offsock(self)
        
    def sendsession(self, msg):
        self.write_message({'type':'session', 'cont':msg})
        
    def sendevent(self, msg, broadcast=False):
        res = {'type':'event', 'cont':msg}
        if broadcast:
            self.control.broadcast(res)
        else:
            self.write_message(res)

    def onevent(self, msg):
        relay = msg.get('relay', None)
        area = msg.get('area', None)
        state = msg.get('state', None)
        if (relay is None and area is None) or state is None:
            misc.logger.info("unexpected event: %s"%(str(msg)))
            return
        if isinstance(state, basestring): state = state.lower().strip()
        if relay:
            self._onrelay(relay, state=='on')

        if area:
            try:
                self.areacon.set(area, state=='on', self._onrelay)
                self.sendevent({'update':{'area':area, 'state':state}}, broadcast=True)
            except Exception, e:
                misc.logger.info("failed to set area: %s"%(str(e)))
                
    def _onrelay(self, relay, state):
        try:
            self.control.device.set(relay-1, state)
            self.sendevent({'update':{'relay':relay, 'state':'on' if state else 'off'}}, broadcast=True)
        except Exception, e:
            misc.logger.info("failed to set relay: %s"%(str(e)))

def periodic_call():
    now = datetime.datetime.now(tz)
    misc.logger.info("periodic %s"%(str(now)))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', help='tornado listen port', required=True, type=int)
    parser.add_argument('-s', '--host', help='tornado host address (default: %(default)s)', default='localhost')
    args = parser.parse_args()
    misc.logger.info('listening on %s:%d'%(args.host, args.port))

    evs = SocketHandler.control

    app = tornado.web.Application([
                                   (r'/data', MainHandler),
                                   (r'/websocket', SocketHandler),
                                   (r'/(index.html)', tornado.web.StaticFileHandler, {"path": loc}),
                                   (r'/ui/(.*)$', tornado.web.StaticFileHandler, {"path": os.path.join(loc, 'ui')}),
                                   (r'/js/(.*)$', tornado.web.StaticFileHandler, {"path": os.path.join(loc, 'js')}),
                                  ], debug=True, cookie_secret=str(uuid.uuid4()))
    
    app.listen(args.port, address=args.host)

    evs.device = controller.SensorControl()
    def scont():
        evs.device.loop(evs)
    th = threading.Thread(target=scont, name='SensorController')
    th.daemon = True
    th.start()

    periodic = tornado.ioloop.PeriodicCallback(periodic_call, 10000)
    
    periodic.start()

    tornado.ioloop.IOLoop.instance().start()
    
if __name__ == "__main__":
    main()
