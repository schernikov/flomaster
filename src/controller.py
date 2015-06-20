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
import misc
try:
    import RPIO
except:
    RPIO = None
    misc.logger.warning('RPIO is not available')

class SensorControl(object):
    def __init__(self):
        if RPIO:
            for pin in self.inpins:
                RPIO.setup(pin, RPIO.IN)
                def on_turn(pin, val): self.on_turn(pin, val)
                RPIO.add_interrupt_callback(pin, on_turn, pull_up_down=RPIO.PUD_DOWN, edge='rising', 
                                            threaded_callback=True)
            
            RPIO.wait_for_interrupts(threaded=True)
            for pin in self.outpins:
                RPIO.setup(pin, RPIO.OUT, initial=RPIO.HIGH)

        self._cond = threading.Condition()
        self._tickcount = 0
        self._polltime = 0.1 # seconds
        self._startstamp = 0
        self._stamp = 0
        self._stopgrace = 1 # seconds

    @property
    def inpins(self):
        return (23,)

    @property
    def outpins(self):
        return (4, 17, 27, 22, 10, 9, 11, 18)

    def set(self, idx, isOn):
        if idx < 0 or idx >= len(self.outpins):
            raise Exception("invalid relay switched: %s"%(str(idx)))
        RPIO.output(self.outpins[idx], RPIO.LOW if isOn else RPIO.HIGH)

    def status(self):
        outs = []; ins = []
        for pin in self.outpins:
            outs.append(RPIO.input(pin) and 'off' or 'on')
        for pin in self.inpins:
            ins.append(RPIO.input(pin) and 'off' or 'on')
        return {'relays':outs, 'sensors':ins}

    def loop(self, evs):
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
                    misc.logger.info("stopping (%d ticks in %.3f seconds)" %(ticks, diff))
                    evs.flow(stop={'ticks':ticks, 'duration':round(diff, 3), 'stamp':stamp})
                    ticks = 0
            else:
                if polltime is None:
                    stopping = False 
                    polltime = self._polltime
                    if stopstamp == 0:
                        misc.logger.info("starting")
                        evs.flow(start={'stamp':startstamp})
                    else:
                        idle = startstamp-stopstamp
                        misc.logger.info("starting (idle for %.3f seconds)" %(idle))
                        evs.flow(start={'idle':round(idle, 3),'stamp':startstamp})
                else:
                    if not stopping:
                        diff = stamp - prevstamp
                        speed = ticksdiff/diff
                        misc.logger.info("%.2f (%d)" % (speed, ticks))
                        evs.flow(counts={'speed':round(speed,3), 'ticks':ticks, 'stamp':stamp})
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

