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
        self._polltime = 0.1
        self._startstamp = 0
        self._stamp = 0

    def loop(self):
        prevticks = 0
        prevstamp = 0
        polltime = None
        stopstamp = 0
        startstamp = 0
        while True:
            self._cond.acquire()
            res = self._cond.wait(polltime); res
            ticks = self._tickcount
            ticksdiff = ticks - prevticks            
            if ticksdiff == 0:  # nothing happened since last poll
                # stopping
                self._tickcount = 0 # setup tick event
                stopstamp = self._stamp
            else:
                if polltime is None: # starting
                    startstamp = self._startstamp
            stamp = self._stamp
            self._cond.release()

            if ticksdiff == 0:
                if polltime:
                    polltime = None
                    print "stopping (%d ticks in %.3f seconds)" %(ticks, stamp-startstamp)
                    ticks = 0
            else:
                if polltime is None: 
                    polltime = self._polltime
                    if stopstamp == 0:
                        print "starting"
                    else:
                        print "starting (idle for %%.3f seconds)" %(startstamp-stopstamp)
                else:
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

