"""
echo "4" > /sys/class/gpio/export
echo "high" > /sys/class/gpio/gpio4/direction
echo "23" > /sys/class/gpio/export
echo "rising" > /sys/class/gpio/gpio23/edge

"""

import time, threading
import RPIO

def on_click(pin, val):
    global laststamp, tickcount
    tickcount += 1
    now = time.time()
    diff = now-laststamp
    if diff >= 0.1:
        print "%.2f" % (tickcount/diff)
        tickcount = 0
        laststamp = now
    # fast, slow, stop states

class SensorControl(object):
    def __init__(self):
        inputpins = [23]
        for pin in inputpins:
            RPIO.setup(pin, RPIO.IN)
            def on_turn(pin, val): self.on_turn(pin, val)
            RPIO.add_interrupt_callback(pin, on_turn, pull_up_down=RPIO.PUD_DOWN, edge='rising', threaded_callback=True)
            
        self._cond = threading.Condition()
        self._tickcount = 0
        self._polltime = 0.1

    def loop(self):
        prevticks = 0
        prevstamp = 0
        polltime = self._polltime
        while True:
            self._cond.acquire()
            res = self._cond.wait(polltime); res
            ticks = self._tickcount
            ticksdiff = ticks - prevticks            
            if ticksdiff == 0:  # nothing happened since last poll
                self._tickcount = 0 # setup tick event
            now = time.time()
            self._cond.release()

            if ticksdiff == 0:
                polltime = None
                print "stopping"
            else:
                if polltime is None: 
                    polltime = self._polltime
                    print "starting"      

            diff = now - prevstamp
            print "%.2f (%d)" % (ticksdiff/diff, ticks)
            prevticks = ticks
            prevstamp = now

    def on_turn(self, pin, val):
        self._cond.acquire()
        if self._tickcount == 0:
            self._cond.notifyAll()
        self._tickcount += 1
        self._cond.release()

