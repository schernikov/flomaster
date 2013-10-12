'''
Created on Oct 9, 2013

@author: schernikov
'''

import os, uuid, argparse, threading
import tornado.ioloop, tornado.web, tornado.websocket
import misc, controller

loc = os.path.normpath(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'web')))

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write({"msg":"Hello, world"})

class SocketControl(object):
    def __init__(self):
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
        
    def write(self, **kargs):
        self.lock.acquire()
        for sock in self.sockset:
            sock.write_message(kargs)
        self.lock.release()

class SocketHandler(tornado.websocket.WebSocketHandler):
    control = SocketControl()

    def open(self):
        misc.logger.info("new socket"+str(self))
        self.control.onsock(self)
        
    def on_message(self, message):
        misc.logger.info("ws: "+message)
        
    def on_close(self):
        misc.logger.info("ws: closed")
        self.control.offsock(self)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', help='tornado listen port', required=True, type=int)
    args = parser.parse_args()
    misc.logger.info('listening on port %d'%(args.port))

    evs = SocketHandler.control

    app = tornado.web.Application([
                                   (r'/data', MainHandler),
                                   (r'/websocket', SocketHandler),
                                   (r'/(index.html)', tornado.web.StaticFileHandler, {"path": loc}),
                                   (r'/ui/(.*)$', tornado.web.StaticFileHandler, {"path": os.path.join(loc, 'ui')}),
                                   (r'/js/(.*)$', tornado.web.StaticFileHandler, {"path": os.path.join(loc, 'js')}),
                                  ], debug=True, cookie_secret=str(uuid.uuid4()))
    
    app.listen(args.port, address='localhost')

    sc = controller.SensorControl()
    def scont():
        sc.loop(evs)
    th = threading.Thread(target=scont, name='SensorController')
    th.daemon = True
    th.start()

    tornado.ioloop.IOLoop.instance().start()
    
if __name__ == "__main__":
    main()
