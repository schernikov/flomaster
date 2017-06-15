'''
Created on Aug 8, 2015

@author: schernikov
'''

import datetime, requests

import configs.server
import Queue, threading
import parts.misc

oneday = 86400 # in seconds

class AreaInfo(object):
    
    def __init__(self, idx, nm):
        self._name = nm
        self._idx = idx
        
    @property
    def name(self):
        return self._name
    
    @property
    def id(self):
        return self._idx
    
    def onliters(self, speed, liters):
        #TODO finish
        #TODO alarm if speed is too high or unusual
        #TODO alarm if watering is going on for too long
        pass

    
class LeakInfo(object):
    
    def __init__(self):
        #TODO finish
        self._liters = 0
        
    def onliters(self, speed, liters, stamp):
        #TODO alarm if leak is too high or small bug going on for too long 
        #TODO alarm if speed is too high or unusual
        self._liters += liters
        
        return self._liters


class Pending(object):
    
    def __init__(self, onstop, area, liters, minutes):
        self._area = area
        self._liters = 0
        self._maxliters = liters
        self._onstop = onstop
        self._stopped = False
        
    @property
    def name(self):
        return self._area.name
    
    @property
    def id(self):
        return self._area.id    

        
    def reset(self, liters, minutes):
        self._maxliters = liters

        
    def onliters(self, speed, liters, stamp):
        self._area.onliters(speed, liters)

        self._liters += liters

        if self._liters >= self._maxliters and not self._stopped:
            self._stopped = True
            self._onstop(self._area)
            
        return self._liters


class Action(object):
    qdepth = 100

    def __init__(self, delay_call, url):
        self._url = url
        self._delay_call = delay_call
        self._q = Queue.Queue(self.qdepth)
        self._th = threading.Thread(target=self._process, name='ActionController')
        self._th.daemon = True
        self._th.start()
        self._notify = self._dummy
        self._onarea = self._dummy
        
        self._areas = {}
        for area in configs.server.areas:
            idx = area[0]
            name = area[1]
            self._areas[idx] = AreaInfo(idx, name)

        self._leak = LeakInfo()

        self._actives = set()
        self._selected = set()
        self._pending = {}


    def _dummy(self, **kvargs): # should never be called
        parts.misc.logger.warn("dummy event notifier: %s" %(str(kvargs)))
    

    def reg_notify(self, notify):
        self._notify = notify
        

    def reg_area(self, onarea):
        self._onarea = onarea
        

    def onstart(self, stamp, idle):
        "called from sensor thread when water counter starts"
        parts.misc.logger.info("starting (idle for %.3f seconds)" %(idle))
        self._notify(start={'idle':round(idle, 3),'stamp':stamp})
    

    def onstop(self, stamp, liters, diffliters, duration):
        "called from sensor thread when water counter stops"
        parts.misc.logger.info("stopping (%d liters in %.3f seconds)" %(liters, duration))
        self._notify(stop={'liters':liters, 'duration':round(duration, 3), 'stamp':stamp})

        self._oncount(diffliters, 0, stamp)


    def oncount(self, stamp, liters, diffliters, speed):
        "called from sensor thread on water counter"
        self._oncount(diffliters, speed, stamp)


    def _qadd(self, name, callback, args=[]):
        try:
            self._q.put((callback, args), block=False)
        except:
            parts.misc.logger.error("failed to put %s into queue"%(name, self._q.qsize()))

                
    def _oncount(self, *args): self._qadd('count', self._qcount, args)


    def _qcount(self, diffliters, speed, stamp):
        "should always be called from queue context"

        div = len(self._actives)
        if div == 0:
            full = self._leak.onliters(speed, diffliters, stamp)
            parts.misc.logger.warn("leak: %.2f  %.4f/%.4f L" % (speed, diffliters, full))
            self._notifyliters(0, stamp, speed, diffliters, full)
        else:
            # distribute liters across currently active areas
            lits = diffliters / div
            sp = speed / div
            for pend in self._actives:
                full = pend.onliters(sp, lits, stamp)
                parts.misc.logger.verbose("'%s' %.2f (%.4f L)" % (pend.name, speed, full))
                self._notifyliters(pend.id, stamp, speed, lits, full)

                
    def _notifyliters(self, idx, stamp, speed, delta, full):
        self._notify(id=idx, counts={'speed':round(speed,4),
                                     'delta':round(delta, 4),
                                     'liters':round(full, 4), 
                                     'stamp':stamp})

    
    def set(self, *args):
        "can be called from scheduled area, manual area or direct manual relay"
        self._qadd('set', self._qset, args)
            

    def _qset(self, idx, isOn):
        "should always be called from queue context"

        area = self._areas.get(idx, None)
        if not area: 
            if idx != configs.server.master:
                parts.misc.logger.warn("unexpected index set: %s" % (str(idx)))
            return

        self._selected.discard(area)

        pend = self._pending.get(area, None)

        if isOn:
            if pend is None:
                liters = configs.server.default_liters
                parts.misc.logger.info("Setting %s for unscheduled '%s'" % (liters, area.name))
                pend = Pending(self._onstop, area, liters)
                self._pending[area] = pend
            
            self._actives.add(pend)
            parts.misc.logger.debug("Set: on '%s'" % (area.name))
        else:
            if pend is None:
                parts.misc.logger.warn("'%s' was not scheduled" % (area.name))
            else:
                del self._pending[area]
                try:
                    self._actives.remove(pend)
                    parts.misc.logger.debug("Set: Off: '%s'" % (area.name))
                except:
                    parts.misc.logger.warn("'%s' was not active" % (area.name))
            
            self._startnext()


    def water(self, *args):
        "called from scheduler on every area to be watered"
        self._qadd('water', self._qwater, args)


    def _qwater(self, pends):
        "should always be called from queue context"

        for area, liters, minutes in pends:
            pend = self._pending.get(area, None)
            if pend is not None:
                parts.misc.logger.info("Area '%s' is already scheduled. Resetting liters to %s (%s minutes)." % (area.name, liters, str(minutes)))
                pend.reset(liters, minutes)
                return
                
            pend = Pending(self._onstop, area, liters, minutes)
            self._pending[area] = pend
        
        self._startnext()
        

    def _startnext(self):
        """can be called either for scheduled area, manual area or direct relay action
           should always be called from queue context"""
        if len(self._actives) > 0 or len(self._pending) == 0: return

        self._select(self._pending.keys())


    def _select(self, areas):
        if self._selected: return
        area = min(areas, key=lambda area: area.id)
        self._selected.add(area)
        parts.misc.logger.debug("Action: starting %s(%d)"%(area.name, area.id))
        self._onarea(area.id, True)
        

    def _onstop(self, area):
        """can be called when active pending is over
           should always be called from queue context"""
        parts.misc.logger.debug("Action: stopping %s(%d)"%(area.name, area.id))
        areas = set(self._pending.keys())
        pend = self._pending.get(area, None)
        acts = self._actives.copy()
        if pend:
            areas.discard(area) # discard currently pending area
            acts.discard(pend)
        if len(acts) == 0 and len(areas) > 0:  # there is nothing else active and there is something pending
            # setting new area will automatically stop current area
            self._select(areas)
        else:
            self._onarea(area.id, False)
        
    
    def _process(self):
        while True:
            callback, args = self._q.get()

            callback(*args)

            self._q.task_done()


    def _scheduled(self):
        #TODO tmp
        #self.reschedule(600)
        #tmp

        pends = []        
        for a in configs.server.areas:
            idx = a[0]
            liters = a[2]
            minutes = a[3] if len(a) > 3 else None
            if not liters: continue
            
            area = self._areas.get(idx, None)
            if area is None:
                parts.misc.logger.warn("unexpected area index requested: %d" % (idx))
                return
            parts.misc.logger.debug("Setting up %s for %.2f liters"%(area.name, liters))
            pends.append((area, liters, minutes))

        self.water(pends)
        
    
    def reschedule(self, override = None):
        now = datetime.datetime.now(configs.server.tz)
        if override:
            seconds = override
        else:
            nxt = now.replace(hour=configs.server.shed_hour, minute=configs.server.shed_minute, second=0, microsecond=0)
            if nxt <= now: nxt += datetime.timedelta(days=1)
            seconds = (nxt-now).total_seconds()
            if seconds > oneday: seconds = oneday
            
        nxt = now + datetime.timedelta(seconds=seconds)
            
        parts.misc.logger.info("re-scheduling in %s"%(parts.misc.second_to_str(seconds), nxt.strftime('%Y-%m-%d %H:%M:%S')))
        self._delay_call(seconds, self._scheduled)
    
        if self._url:
            try:
                # kick something outside to announce it is alive  
                requests.get(self._url, timeout=1)
            except:
                parts.misc.logger.warn("failed to report rescheduling to %s"%(self._url))

