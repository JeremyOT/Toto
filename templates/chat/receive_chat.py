#!/usr/bin/env python

import urllib2
import json
import multiprocessing

def listen(port):
  print "Listening on %d" % port
  print urllib2.urlopen('http://localhost:%d' % port, json.dumps({'method': 'receive_message', 'parameters': {}})).read()
  print "Received from %d" % port

p1 = multiprocessing.Process(target=listen, args=(8888,))
p2 = multiprocessing.Process(target=listen, args=(8889,))
p1.start()
p2.start()
p1.join()
p2.join()
