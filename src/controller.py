"""
echo "4" > /sys/class/gpio/export
echo "high" > /sys/class/gpio/gpio4/direction
echo "23" > /sys/class/gpio/export
echo "rising" > /sys/class/gpio/gpio23/edge

"""

import time, threading
import RPIO

class SensorControl(object):
    def __init__(self):
        inputpins = [23]
        for pin in inputpins:
            RPIO.setup(pin, RPIO.IN)
            def on_turn(pin, val): self.on_turn(pin, val)
            RPIO.add_interrupt_callback(pin, on_turn, pull_up_down=RPIO.PUD_DOWN, edge='rising', threaded_callback=True)
            
        RPIO.wait_for_interrupts(threaded=True)

        self._cond = threading.Condition()
        self._tickcount = 0
        self._polltime = 0.1 # seconds
        self._startstamp = 0
        self._stamp = 0
        self._stopgrace = 1 # seconds

    def loop(self):
        prevticks = 0
        prevstamp = 0
        polltime = None
        stopstamp = 0
        startstamp = 0
        stopping = False
        needstop = False
        while True:
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
            stamp = self._stamp
            self._cond.release()

            if needstop:
                needstop = False
                stopping = False
                if polltime:
                    polltime = None
                    print "stopping (%d ticks in %.3f seconds)" %(ticks, stamp-startstamp)
                    ticks = 0
            else:
                if polltime is None:
                    stopping = False 
                    polltime = self._polltime
                    if stopstamp == 0:
                        print "starting"
                    else:
                        print "starting (idle for %.3f seconds)" %(startstamp-stopstamp)
                else:
                    if not stopping:
                        diff = stamp - prevstamp
                        print "%.2f (%d)" % (ticksdiff/diff, ticks)
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

