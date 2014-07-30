import unittest
import urllib2
import json
import os
import signal
from uuid import uuid4
from toto.secret import *
from multiprocessing import Process, active_children
from toto.server import TotoServer
from toto.handler import TotoHandler
from time import sleep, time
import cProfile

class ProfileManager(object):
  def __init__(self):
    self.profile = cProfile.Profile()
    self.profile.enable()

  def invoke(self, handler, params):
    self.profile.disable()
    self.profile.print_stats('cumtime')

def run_server(processes=1):
  server = TotoServer(method_module='web_methods', port=9000, processes=processes)
  profile = ProfileManager()
  print TotoHandler.__dict__.keys()
  TotoHandler._TotoHandler__method_root.printprof = profile
  server.run()

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
    for i in xrange(1000):
      f = urllib2.urlopen(req)
      f.close()
    total = time() - start
    req = urllib2.Request('http://127.0.0.1:9000/', json.dumps({'method': 'printprof', 'parameters':{}}), headers)
    urllib2.urlopen(req)
    print '1000 requests in %s seconds\nAverage time %s ms (%s requests/second)' % (total, total/1000.0*1000.0, 1000.0/total)
