'''
Created on Aug 11, 2015

@author: schernikov
'''

import threading
import configs.server


class AreaControl(object):

    @classmethod
    def info(cls):
        return [[a[0], a[1]] for a in configs.server.areas]


    def __init__(self):
        self._active = None
        self._lock = threading.RLock()
        self._onrelay = None

    def register(self, onrelay):
        self._onrelay = onrelay
        
    def state(self):
        'return currently active index or None'
        return self._active

    
    def set(self, index, active):
        if not active:
            if self._active == index:
                self._active = None
              
                self._onset((index, False), (configs.server.master, False))
            return
        
        if self._active is None:
            self._active = index
            
            self._onset((configs.server.master, True), (index, True))
            return
        
        self._onset((index, True), (self._active, False))

        self._active = index


    def _onset(self, args1, args2):
        self._lock.acquire()
        
        self._onrelay(*args1)
        self._onrelay(*args2)
        
        self._lock.release()

