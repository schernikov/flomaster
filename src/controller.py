"""
echo "4" > /sys/class/gpio/export
echo "high" > /sys/class/gpio/gpio4/direction
echo "23" > /sys/class/gpio/export
echo "rising" > /sys/class/gpio/gpio23/edge

"""

import time

tickcount = 0
laststamp = 0

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
