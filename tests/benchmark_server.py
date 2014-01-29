import unittest
import urllib2
import json
import os
import signal
from uuid import uuid4
from toto.secret import *
from multiprocessing import Process, active_children
from toto.server import TotoServer
from time import sleep, time

def run_server(processes=1):
  TotoServer(method_module='web_methods', port=9000, processes=processes).run()

class TestWeb(unittest.TestCase):
  
  @classmethod
  def setUpClass(cls):
    print 'Starting server'
    cls.service_process = Process(target=run_server, args=[1])
    cls.service_process.start()
    sleep(0.5)
  
  @classmethod
  def tearDownClass(cls):
    print 'Stopping server'
    processes = [int(l.split()[0]) for l in os.popen('ps').readlines() if 'python' in l and 'unittest' in l]
    for p in processes:
      if p == os.getpid():
        continue
      print 'killing', p
      os.kill(p, signal.SIGKILL)
    sleep(0.5)
  
  def test_method(self):
    request = {}
    request['method'] = 'test.ok'
    request['parameters'] = {'arg1': 1, 'arg2': 'hello'}
    headers = {'content-type': 'application/json'}
    req = urllib2.Request('http://127.0.0.1:9000/', json.dumps(request), headers)
    start = time()
    for i in xrange(10000):
      f = urllib2.urlopen(req)
    total = time() - start
    print '10000 requests in %s seconds\nAverage time %s ms (%s requests/second)' % (total, total/10000.0*1000.0, 10000.0/total)

