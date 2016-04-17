'''
Created on Aug 11, 2015

@author: schernikov
'''

import threading

import configs.server
import parts.misc

def genevent(msg):
    return {'type':'event', 'cont':msg}

class SessionControl(object):
    
    def __init__(self, act, relays, area):
        self.sockset = set()
        self.lock = threading.RLock()
        self._action = act
        self._relays = relays
        self._area = area
        act.reg_notify(self.notify)
        act.reg_area(self.onarea)
        area.register(self.onrelay)
        
    def onsession(self, sock):
        self.lock.acquire()
        self.sockset.add(sock)
        self.lock.release()
        
        dstat = self._relays.status()
        ainfo = self._area.info()
        active = self._area.state()
        dstat.update({'areas':ainfo, 'master':configs.server.master})
        if active: dstat['active'] = active
        
        return genevent({'init':dstat})
        
    def offsession(self, sock):
        self.lock.acquire()
        self.sockset.discard(sock)
        self.lock.release()
    
    def notify(self, **kargs):
        self.broadcast({'type':'flow', 'cont':kargs})

    def broadcast(self, dd, skip=None):
        self.lock.acquire()
        for sock in self.sockset:
            if sock == skip: continue
            sock.write_message(dd)
        self.lock.release()
        
    def onrelay(self, relay, state):
        try:
            self._relays.set(relay-1, state)
            self._action.set(relay, state)
            self.anounce('relay', relay, state)
        except Exception, e:
            parts.misc.logger.info("failed to set relay: %s"%(str(e)))
            
    def onarea(self, idx, state):
        try:
            self._area.set(idx, state)
            self.anounce('area', idx, state)
        except Exception, e:
            parts.misc.logger.info("failed to set area: %s"%(str(e)))
            
    def anounce(self, nm, idx, state):
        self.broadcast(genevent({'update':{nm:idx, 'state':'on' if state else 'off'}}))

