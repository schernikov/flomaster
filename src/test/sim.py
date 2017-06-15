'''
Created on Aug 11, 2015

@author: schernikov
'''

import threading, time

import configs.server

class RPIOSim(object):
    sleeping = 0.003
    LOW = True
    HIGH = False

    def __init__(self):
        self._flowing = False
        self._master = configs.server.outpins[configs.server.master-1]
        self._masteron = False
        self._flowpins = set()

    def setup(self, callback):
        self._callback = callback
        self._cond = threading.Condition()
        th = threading.Thread(target=self._process, name=self.__class__.__name__, args=(callback,))
        th.daemon = True
        th.start()
    
    def output(self, pin, isLow):
        print "GPIO: %d %s"%(pin,isLow)
        #=======================================================================
        # import traceback
        # traceback.print_stack()
        #=======================================================================
        
        if self._master == pin:
            self._masteron = isLow
        else:
            if isLow:
                self._flowpins.add(pin)
            else:
                self._flowpins.discard(pin)
        
        if self._masteron and len(self._flowpins) > 0:
            self._cond.acquire()
            self._flowing = True
            self._cond.notifyAll()
            self._cond.release()
        else:
            self._flowing = False

    
    def input(self, pin):
        return self.LOW # == 'off'
    
    
    def cleanup(self):
        pass
    

    def _process(self, callback):
        while True:
            print "GPIO: waiting",self._flowing
            self._cond.acquire()
            while not self._flowing:
                self._cond.wait()
            self._cond.release()
            print "GPIO: ready",self._flowing
            
            while self._flowing:
                time.sleep(self.sleeping)
                callback(0, True)
