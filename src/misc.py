'''
Created on Oct 9, 2013

@author: schernikov
'''

import logging, sys, urlparse, urllib, os
import tornado

logger = logging.getLogger('flomaster')

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format='%(asctime)s %(levelname)s:%(message)s', datefmt='%H:%M:%S')

class Base(object):
    def __init__(self, pref):
        self._pref = pref
        self._handlers = []
    @property
    def pref(self):
        return self._pref

    def url(self, u):
        def decor(klass):
            self._handlers.append(klass)
            klass._base = self
            klass._url = u
            def base_url(cls, prms=None):
                u = cls._base.geturl(cls._url)
                if prms:
                    return urlparse.urlunparse(('', '', u, '', urllib.urlencode(prms), ''))            
                return u
            setattr(klass, 'base_url', classmethod(base_url))
            return klass
        return decor

    def geturl(self, u):
        return r"%s%s"%(self.pref, u)
    
    def handlers(self, loc, statics = []):
        hdls = []
        for k in self._handlers:
            hdls.append((self.geturl(k._url), k))
        for st in statics:
            hdls.append((r"%s%s/(.*)"%(self.pref, st), tornado.web.StaticFileHandler, {"path": os.path.join(loc, st)}))
        return hdls

base = Base('/')
