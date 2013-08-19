import unittest
import urllib2
import json
import os
import signal
from uuid import uuid4
from toto.secret import *
from multiprocessing import Process, active_children
from toto.worker import TotoWorkerService
from toto.workerconnection import WorkerConnection
from time import sleep, time

def run_server(port):
  TotoWorkerService(method_module='worker_methods', worker_bind_address='tcp://*:%d' % port, debug=True).run()

def dicts_equal(d1, d2):
  for k, v in d1.iteritems():
    if v != d2[k]:
      return False
  return len(d1) == len(set(d1.keys()) | set(d2.keys()))

def invoke_synchronously(worker, method, parameters, **kwargs):
  resp = []
  def cb(response):
    resp.append(response)
  worker.invoke(method, parameters, callback=cb, **kwargs)
  while not resp:
    sleep(0.1)
  return resp[0]

class TestWorker(unittest.TestCase):
  
  @classmethod
  def setUpClass(cls):
    print 'Starting worker'
    cls.service_process = Process(target=run_server, args=[9001])
    cls.service_process.start()
    sleep(0.5)
    cls.worker = WorkerConnection('tcp://127.0.0.1:9001')
  
  @classmethod
  def tearDownClass(cls):
    print 'Stopping worker', cls.service_process.pid
    for p in active_children():
      print 'Killing', p.pid
      os.kill(p.pid, signal.SIGTERM)
      os.kill(p.pid + 1, signal.SIGTERM)
      os.kill(p.pid + 2, signal.SIGTERM)
    sleep(0.5)
  
  def test_method(self):
    resp = []
    def cb(response):
      resp.append(response)
    parameters = {'arg1': 1, 'arg2': 'hello'}
    self.worker.invoke('return_value', parameters, callback=cb)
    while not resp:
      sleep(0.1)
    self.assertTrue(dicts_equal(parameters, resp[0]['parameters']))
  
  def test_method_alt_invocation(self):
    resp = []
    def cb(response):
      resp.append(response)
    parameters = {'arg1': 1, 'arg2': 'hello'}
    self.worker.return_value(parameters, callback=cb)
    while not resp:
      sleep(0.1)
    self.assertTrue(dicts_equal(parameters, resp[0]['parameters']))
  
  def test_bad_method(self):
    resp = []
    def cb(response):
      resp.append(response)
    parameters = {'arg1': 1, 'arg2': 'hello'}
    self.worker.invoke('bad_method', parameters, callback=cb)
    while not resp:
      sleep(0.1)
    self.assertTrue(resp[0]['error']['code'] == 1000)
    self.assertTrue(resp[0]['error']['value'] == "'module' object has no attribute 'bad_method'")

  def test_exception(self):
    resp = []
    def cb(response):
      resp.append(response)
    parameters = {'arg1': 1, 'arg2': 'hello'}
    self.worker.invoke('throw_exception', parameters, callback=cb)
    while not resp:
      sleep(0.1)
    self.assertTrue(resp[0]['error']['code'] == 1000)
    self.assertTrue(resp[0]['error']['value'] == "Test Exception")

  def test_toto_exception(self):
    resp = []
    def cb(response):
      resp.append(response)
    parameters = {'arg1': 1, 'arg2': 'hello'}
    self.worker.invoke('throw_toto_exception', parameters, callback=cb)
    while not resp:
      sleep(0.1)
    self.assertTrue(resp[0]['error']['code'] == 4242)
    self.assertTrue(resp[0]['error']['value'] == "Test Toto Exception")


