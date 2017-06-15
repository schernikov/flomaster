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
areas = ((2, u"Газон", 380, 24),
         (4, u"Фронт (выкл)", 0, 0),
         (5, u"Фронт Цветы", 800, 9),
         (3, u"Горшки", 1200, 10),
         (7, u"Помидоры", 1200, 12))


ticks2liters=0.003355

default_liters = 100
default_minutes = 5

tz = pytz.timezone('US/Pacific')

debug = False