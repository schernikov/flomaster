'''
Created on Mar 23, 2013

@author: schernikov
'''

sleeper = 2000      # ms; how often to check for wakeup state 
period = sleeper*2  # ms; when to trigger woke up status
poll = 600000       # ms; ping-pong frequency
span = 60000        # ms; when to consider socket bouncing
longspan = span*2   # ms; socked it lived long enough, okay to restart right away 
pingtimeout = 3000  # ms; 
