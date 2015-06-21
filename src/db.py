'''
Created on Jun 20, 2015

@author: schernikov
'''

import pymongo
import misc

class DB(object):
    dbname = 'garden'
        
    def __init__(self, spec):
        if not spec:
            misc.logger.warn('MmongoDB is not specified')
            return
        hostname, port = spec
        self._db = None
        try:
            cl = pymongo.MongoClient(hostname, port)
        except Exception, e:
            misc.logger.warn('Can not connect to mongoDB: %s'%(str(e)))
            return
        try:
            self._db = cl[self.dbname]
        except:
            misc.logger.warn('DB %s is not in %s'%(self.dbname, self._url))
            return
        
    def getcollection(self, collname):
        if not self._db: return None
        try:
            coll = self._db[collname]
        except:
            misc.logger.warn('Collection %s is not in db'%(collname))
            return None
    
        return coll

def main():
    db = DB(('raspberrypi', 27017))
    print db

if __name__ == '__main__':
    main()