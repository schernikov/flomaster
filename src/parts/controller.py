#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
echo "4" > /sys/class/gpio/export
echo "high" > /sys/class/gpio/gpio4/direction
echo "23" > /sys/class/gpio/export
echo "rising" > /sys/class/gpio/gpio23/edge

"""

"""
15117 ticks, 97 seconds, 50.7 liters 
"""

import time, threading
import configs.server
import parts.misc


def setup(callback):
    for pin in configs.server.inpins:
        RPIO.setup(pin, RPIO.IN)
        RPIO.add_interrupt_callback(pin, callback, pull_up_down=RPIO.PUD_DOWN, edge='rising', 
                                    threaded_callback=True)
    
    RPIO.wait_for_interrupts(threaded=True)
    for pin in configs.server.outpins:
        RPIO.setup(pin, RPIO.OUT, initial=RPIO.HIGH)

try:
    import RPIO
except:
    configs.server.debug = True
    import test.sim
    RPIO = test.sim.RPIOSim()
    def setup(callback): 
        RPIO.setup(callback)

    parts.misc.logger.warning('RPIO is not available. Switching to simulated RPIO.')

class RelayControl(object):
    
    def __init__(self):
        self._names = {}
        for a in configs.server.areas:
            self._names[a[0]-1] = a[1]

    def set(self, idx, isOn):
        if idx < 0 or idx >= len(configs.server.outpins):
            raise Exception("invalid relay switched: %s"%(str(idx)))
        
        nm = self._names.get(idx, None)
        if nm: parts.misc.logger.info("%s %s" %('starting' if isOn else 'stopping', nm))

        RPIO.output(configs.server.outpins[idx], RPIO.LOW if isOn else RPIO.HIGH)

    def status(self):
        outs = []; ins = []
        for pin in configs.server.outpins:
            outs.append(RPIO.input(pin) and 'off' or 'on')
        for pin in configs.server.inpins:
            ins.append(RPIO.input(pin) and 'off' or 'on')
        return {'relays':outs, 'sensors':ins}


class SensorControl(object):
    
    def __init__(self, action):
        setup(self.on_turn)

        self._cond = threading.Condition()
        self._tickcount = 0
        self._polltime = 0.5 # seconds
        self._startstamp = 0
        self._stamp = 0
        self._stopgrace = 1 # seconds

        th = threading.Thread(target=self._loop, name=self.__class__.__name__, args=(action,))
        th.daemon = True
        th.start()

    def _loop(self, act):
        prevticks = 0
        prevstamp = 0
        polltime = None
        stopstamp = 0
        startstamp = 0
        stopping = False
        needstop = False
        while True:
            #
            # critical area
            #
            self._cond.acquire()
            res = self._cond.wait(polltime); res
            ticks = self._tickcount
            ticksdiff = ticks - prevticks            
            if ticksdiff == 0:  # nothing happened since last poll
                now = time.time()
                stopping = True
                stopstamp = self._stamp
                if (stopstamp+self._stopgrace) <= now:
                    needstop = True
                    self._tickcount = 0 # setup tick event
            else:
                if polltime is None: # starting
                    startstamp = self._startstamp
                else:
                    if stopping: stopping = False
                    
            stamp = self._stamp
            self._cond.release()
            # 
            # end of critical area
            #
            if needstop:
                needstop = False
                stopping = False
                if polltime:
                    polltime = None
                    diff = stamp-startstamp
                    act.onstop(stamp, ticks*configs.server.ticks2liters, diff)
                    ticks = 0
            else:
                if polltime is None:
                    stopping = False 
                    polltime = self._polltime
                    if stopstamp == 0:
                        act.onstart(startstamp, 0)
                    else:
                        idle = startstamp-stopstamp
                        act.onstart(startstamp, idle)
                else:
                    if not stopping:
                        diff = stamp - prevstamp
                        if diff > 0:
                            liters = ticksdiff*configs.server.ticks2liters
                            speed = liters/diff
                            act.oncount(stamp, ticks*configs.server.ticks2liters, liters, speed)

            prevticks = ticks
            prevstamp = stamp

    def on_turn(self, pin, val):
        self._cond.acquire()
        self._stamp = time.time()
        if self._tickcount == 0:
            self._cond.notifyAll()
            self._startstamp = self._stamp
        self._tickcount += 1
        self._cond.release()

