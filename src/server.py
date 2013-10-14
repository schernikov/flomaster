'''
Created on Oct 9, 2013

@author: schernikov
'''

import os, uuid, argparse, threading, json
import tornado.ioloop, tornado.web, tornado.websocket
import misc, controller, configs.client

loc = os.path.normpath(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'web')))

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

def convert(mod):
    d = {}
    for nm in dir(mod):
        if nm.startswith('_'): continue
        d[nm] = getattr(mod, nm)
    return d

class SocketHandler(tornado.websocket.WebSocketHandler):
    control = DevControl()

    def open(self):
        misc.logger.info("new socket"+str(self))
        self.control.onsock(self)
        self.sendsession({'init':convert(configs.client)})
        status = self.control.device.status()
        self.sendevent({'init':status})
        
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
            self.control.broadcast(res, skip=self)
        else:
            self.write_message(res)

    def onevent(self, msg):
        relay = msg.get('relay', None)
        state = msg.get('state', None)
        if relay is None or state is None:
            misc.logger.info("unexpected event: %s"%(str(msg)))
            return
        if isinstance(state, basestring):
            state = state.lower().strip()
        idx = relay-1
        try:
            self.control.device.set(idx, state=='on')
            self.sendevent({'update':{'relay':relay, 'state':state}}, broadcast=True)
        except Exception, e:
            misc.logger.info("failed to set relay: %s"%(str(e)))

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

    tornado.ioloop.IOLoop.instance().start()
    
if __name__ == "__main__":
    main()
