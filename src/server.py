'''
Created on Oct 9, 2013

@author: schernikov
'''

import tornado.ioloop, tornado.web, os, uuid, argparse
import misc

loc = os.path.join(os.path.dirname(__file__), '..', 'web')

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write({"msg":"Hello, world"})

app = tornado.web.Application([
                               (r'/data', MainHandler),
                              ], debug=True, cookie_secret=str(uuid.uuid4()))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', help='tornado listen port', required=True, type=int)
    args = parser.parse_args()
    misc.logger.info('listening on port %d'%(args.port))
    app.listen(args.port, address='localhost')

    tornado.ioloop.IOLoop.instance().start()
