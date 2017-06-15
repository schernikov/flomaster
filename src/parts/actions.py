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
        self._end = None
        self._duration = datetime.timedelta(minutes=minutes)
        
    @property
    def name(self):
        return self._area.name
    
    @property
    def id(self):
        return self._area.id    


    def activate(self):
        now = datetime.datetime.now(configs.server.tz)
        self._end = now + self._duration


    def check_expired(self, now):
        if self._stopped or self._end > now: return
        # it is expired and still going; let's stop it now
        self._stopped = True
        self._onstop(self._area)

        
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


    def check_expired(self):
        now = datetime.datetime.now(configs.server.tz)
        self._qadd('tick', self._qtick, (now,))


    def _qadd(self, name, callback, args=[]):
        try:
            self._q.put((callback, args), block=False)
        except:
            parts.misc.logger.error("failed to put %s into queue"%(name, self._q.qsize()))


    def _qtick(self, now):
        "should always be called from queue context; validates active jobs expiration"
        for pend in self._actives:
            pend.check_expired(now)

                
    def _oncount(self, *args): 
        self._qadd('count', self._qcount, args)


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
                minutes = configs.server.default_minutes
                parts.misc.logger.info("Setting %s liters (%d minutes) for unscheduled '%s'" % (liters, minutes, area.name))
                pend = Pending(self._onstop, area, liters, minutes)
                self._pending[area] = pend
            
            pend.activate()
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
                parts.misc.logger.info("Area '%s' is already scheduled. Resetting to %s liters (%s minutes)." % (area.name, liters, str(minutes)))
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

            try:
                callback(*args)
            except Exception, e:
                parts.misc.logger.warn("Action processing failure: %s"%(str(e)))
            finally:
                self._q.task_done()


    def _scheduled(self, stamp, retry):
        self._reschedule(stamp, retry)

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
        
    
    def schedule(self, start_time, retry):
        seconds, next_time = get_next_time(start_time, retry)

        parts.misc.logger.info("Starting in %s. Retrying every %s."%(parts.misc.second_to_str(seconds),
                                                                    parts.misc.second_to_str(retry.total_seconds())))

        self._apply_schedule(seconds, next_time, retry)

    
    def _reschedule(self, stamp, retry):
        seconds, next_time = get_next_time(stamp, retry)
            
        parts.misc.logger.info("re-scheduling in %s (%s)"%(parts.misc.second_to_str(seconds), 
                                                           next_time.strftime('%Y-%m-%d %H:%M:%S')))
        self._apply_schedule(seconds, next_time, retry)


    def _apply_schedule(self, seconds, next_time, retry):
        self._delay_call(seconds, lambda : self._scheduled(next_time, retry))

        if self._url:
            try:
                # kick something outside to announce it is alive  
                requests.get(self._url, timeout=1)
            except:
                parts.misc.logger.warn("failed to report rescheduling to %s"%(self._url))



def get_next_time(start_time, retry):
    now = datetime.datetime.now(configs.server.tz)
    if start_time:
        if start_time < now:
            count = int((now - start_time).total_seconds()/retry.total_seconds())
            start_time += retry*count
            if start_time < now: start_time += retry

            parts.misc.logger.info("Missed start time. Rescheduling for %s"%(str(start_time)))
        seconds = (start_time - now).total_seconds()
        next_time = start_time
    else:
        seconds = retry.total_seconds()
        next_time = now+retry
        
    return seconds, next_time
