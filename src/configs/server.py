#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Created on Aug 9, 2015

@author: schernikov
'''

import pytz

inpins = (23,)
outpins = (4, 17, 27, 22, 10, 9, 11, 18)

master = 1
areas = ((2, u"Газон", 80),
         (4, u"Фронт (выкл)", 0),
         (5, u"Фронт Цветы", 50),
         (3, u"Горшки", 100),
         (7, u"Помидоры", 100))

ticks2liters=0.003355

shed_hour = 4
shed_minute = 0
tz = pytz.timezone('US/Pacific')

debug = False