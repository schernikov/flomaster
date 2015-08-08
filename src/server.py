#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Created on Oct 9, 2013

@author: schernikov
'''

import os, uuid, argparse, threading, json, datetime, pytz
import tornado.ioloop, tornado.web, tornado.websocket, requests
import misc, controller, configs.client

loc = os.path.normpath(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'web')))

tz = pytz.timezone('US/Pacific')
oneday = 86400 # in seconds
shed_hour = 4
shed_minute = 0


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write({"msg":"Hello, world"})

class DevControl(object):
    @classmethod
    def genevent(self, msg):
        return {'type':'event', 'cont':msg}
    
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
        
    def switch(self, relay, state):
        try:
            self.device.set(relay-1, state)
            self.anounce('relay', relay, state)
        except Exception, e:
            misc.logger.info("failed to set relay: %s"%(str(e)))
            
    def anounce(self, nm, idx, state):
        self.broadcast(self.genevent({'update':{nm:idx, 'state':'on' if state else 'off'}}))


class AreaControl(object):

    @classmethod
    def info(cls):
        return [[a[0], a[1]] for a in controller.areas]

    def __init__(self, control):
        self._active = None
        self._lock = threading.RLock()
        self._control = control
        
    def state(self):
        'return currently active index or None'
        return self._active
    
    def set(self, index, active):
        if not active:
            if self._active == index:
                self._active = None
              
                self._onset((index, False), (controller.master, False))
            return
        
        if self._active is None:
            self._active = index
            
            self._onset((controller.master, True), (index, True))
            return
        
        self._onset((self._active, False), (index, True))

        self._active = index

    def _onset(self, args1, args2):
        self._lock.acquire()
        
        self._control.switch(*args1)
        self._control.switch(*args2)
        
        self._lock.release()
        
    def switch(self, area, state):
        try:
            self.set(area, state)
            self._control.anounce('area', area, state)
        except Exception, e:
            misc.logger.info("failed to set area: %s"%(str(e)))
        
    def start(self, idx):
        self.switch(idx, True)
        
    def stop(self, idx):
        self.switch(idx, False)


def convert(mod):
    d = {}
    for nm in dir(mod):
        if nm.startswith('_'): continue
        d[nm] = getattr(mod, nm)
    return d

class SocketHandler(tornado.websocket.WebSocketHandler):
    control = DevControl()
    areacon = AreaControl(control)

    def open(self):
        misc.logger.info("new socket"+str(self))
        self.control.onsock(self)
        self.sendsession({'init':convert(configs.client)})
        dstat = self.control.device.status()
        ainfo = self.areacon.info()
        dstat.update({'areas':ainfo, 'master':controller.master})
        active = self.areacon.state()
        if active: dstat['active'] = active

        self.write_message(self.control.genevent({'init':dstat}))
        
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
        
    def onevent(self, msg):
        relay = msg.get('relay', None)
        area = msg.get('area', None)
        state = msg.get('state', None)
        if (relay is None and area is None) or state is None:
            misc.logger.info("unexpected event: %s"%(str(msg)))
            return
        if isinstance(state, basestring): state = state.lower().strip()
        if relay:
            self.control.switch(relay, state=='on')

        if area:
            self.areacon.switch(area, state=='on')
                

def shed_stop(control, area, pos):
    control.stop(area)
    shed_start(control, pos)

def scheduled(control, url):
    reschedule(control, url)
    shed_start(control, 0)

def shed_start(control, pos):
    if pos >= len(controller.areas): return
        
    inst = tornado.ioloop.IOLoop.instance()
    a = controller.areas[pos]
    pos += 1
    
    area = a[0]
    nm = a[1]
    seconds = a[2]

    if seconds > 0:
        misc.logger.info("shed: starting %s"%(nm))
        control.start(area)
        inst.call_later(seconds, shed_stop, control, area, pos)
    else:
        shed_start(control, pos)

def reschedule(control, url):
    now = datetime.datetime.now(tz)
    nxt = now.replace(hour=shed_hour, minute=shed_minute, second=0, microsecond=0)
    if nxt <= now: nxt = nxt.replace(day=now.day+1)
    seconds = (nxt-now).total_seconds()
    if seconds > oneday: seconds = oneday
        
    misc.logger.info("re-scheduling in %s"%(seconds))
    tornado.ioloop.IOLoop.instance().call_later(seconds, scheduled, control, url)

    if url:
        try:
            # kick something outside to announce it is alive  
            requests.get(url, timeout=1)
        except:
            pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', help='tornado listen port', required=True, type=int)
    parser.add_argument('-n', '--ping', help='url to ping')
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
                                  ], debug=False, cookie_secret=str(uuid.uuid4()))
    
    app.listen(args.port, address=args.host)

    evs.device = controller.SensorControl()
    def scont():
        evs.device.loop(evs)
    th = threading.Thread(target=scont, name='SensorController')
    th.daemon = True
    th.start()

    reschedule(SocketHandler.areacon, args.ping)

    tornado.ioloop.IOLoop.instance().start()
    
if __name__ == "__main__":
    main()
