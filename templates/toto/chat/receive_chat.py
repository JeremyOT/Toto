#!/usr/bin/env python

import urllib2
import json
import multiprocessing

def listen(port):
  print "Listening on %d" % port
  print urllib2.urlopen(urllib2.Request('http://localhost:%d' % port, json.dumps({'method': 'receive_message', 'parameters': {}}), {'content-type': 'application/json'})).read()
  print "Received from %d" % port

def listen_url(port):
  print "Listening on %d" % port
  print urllib2.urlopen(urllib2.Request('http://localhost:%d/receive_message' % port, headers={'content-type': 'application/json'})).read()
  print "Received from %d" % port

p1 = multiprocessing.Process(target=listen, args=(8888,))
p2 = multiprocessing.Process(target=listen, args=(8889,))
p3 = multiprocessing.Process(target=listen_url, args=(8888,))
p4 = multiprocessing.Process(target=listen_url, args=(8889,))
p1.start()
p2.start()
p3.start()
p4.start()
p1.join()
p2.join()
p3.join()
p4.join()
