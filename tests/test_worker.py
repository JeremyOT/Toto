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
from tornado.gen import coroutine
from tornado.concurrent import Future
from tornado.ioloop import IOLoop
from time import sleep, time
from threading import Thread

def run_loop(func):
  def wrapper():
    ioloop = IOLoop()
    @coroutine
    def looped():
      yield func()
      ioloop.stop()
    ioloop.add_callback(looped)
    thread = Thread(target=ioloop.start)
    thread.start()
  return wrapper

def run_server(port, daemon='start'):
  TotoWorkerService(method_module='worker_methods', worker_bind_address='tcp://*:%d' % port, worker_socket_address='ipc:///tmp/workerservice%d.sock' % port, control_socket_address='ipc:///tmp/workercontrol%d.sock', debug=True, daemon=daemon, pidfile='worker-%d.pid' % port).run()

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
    for p in [Process(target=run_server, args=[9001 + i]) for i in xrange(3)]:
      p.start()
    sleep(0.5)
    cls.worker_addresses = ['tcp://127.0.0.1:%d' % (9001 + i) for i in xrange(3)]
    cls.worker = WorkerConnection(cls.worker_addresses[0])

  @classmethod
  def tearDownClass(cls):
    print 'Stopping worker'
    for p in [Process(target=run_server, args=[9001 + i, 'stop']) for i in xrange(3)]:
      p.start()
    sleep(0.5)
  
  def test_method(self):
    resp = []
    def cb(response):
      resp.append(response)
    parameters = {'arg1': 1, 'arg2': 'hello'}
    self.worker.invoke('return_value', parameters, callback=cb)
    while not resp:
      sleep(0.1)
    self.assertEqual(parameters, resp[0]['parameters'])

  def test_method_generator(self):
    resp = []
    parameters = {'arg1': 1, 'arg2': 'hello'}
    @run_loop
    @coroutine
    def run():
      resp.append((yield self.worker.invoke('return_value', parameters, await=True)))
    run()
    while not resp:
      sleep(0.1)
    self.assertEqual(parameters, resp[0]['parameters'])
  
  def test_method_alt_invocation(self):
    resp = []
    def cb(response):
      resp.append(response)
    parameters = {'arg1': 1, 'arg2': 'hello'}
    self.worker.return_value(parameters, callback=cb)
    while not resp:
      sleep(0.1)
    self.assertEqual(parameters, resp[0]['parameters'])
  
  def test_method_alt_invocation_generator(self):
    resp = []
    parameters = {'arg1': 1, 'arg2': 'hello'}
    @run_loop
    @coroutine
    def run():
      resp.append((yield self.worker.return_value(parameters, await=True)))
    run()
    while not resp:
      sleep(0.1)
    self.assertEqual(parameters, resp[0]['parameters'])
  
  def test_bad_method(self):
    resp = []
    def cb(response):
      resp.append(response)
    parameters = {'arg1': 1, 'arg2': 'hello'}
    self.worker.invoke('bad_method', parameters, callback=cb)
    while not resp:
      sleep(0.1)
    self.assertEqual(resp[0]['error']['code'], 1000)
    self.assertEqual(resp[0]['error']['value'], "'module' object has no attribute 'bad_method'")

  def test_exception(self):
    resp = []
    def cb(response):
      resp.append(response)
    parameters = {'arg1': 1, 'arg2': 'hello'}
    self.worker.invoke('throw_exception', parameters, callback=cb)
    while not resp:
      sleep(0.1)
    self.assertEqual(resp[0]['error']['code'], 1000)
    self.assertEqual(resp[0]['error']['value'], "Test Exception")

  def test_exception_generator(self):
    resp = []
    parameters = {'arg1': 1, 'arg2': 'hello'}
    @run_loop
    @coroutine
    def run():
      resp.append((yield self.worker.invoke('throw_exception', parameters, await=True)))
    run()
    while not resp:
      sleep(0.1)
    self.assertEqual(resp[0]['error']['code'], 1000)
    self.assertEqual(resp[0]['error']['value'], "Test Exception")

  def test_toto_exception(self):
    resp = []
    def cb(response):
      resp.append(response)
    parameters = {'arg1': 1, 'arg2': 'hello'}
    self.worker.invoke('throw_toto_exception', parameters, callback=cb)
    while not resp:
      sleep(0.1)
    self.assertEqual(resp[0]['error']['code'], 4242)
    self.assertEqual(resp[0]['error']['value'], "Test Toto Exception")

  def test_toto_exception_generator(self):
    resp = []
    @run_loop
    @coroutine
    def run():
      parameters = {'arg1': 1, 'arg2': 'hello'}
      resp.append((yield self.worker.invoke('throw_toto_exception', parameters, await=True)))
    run()
    while not resp:
      sleep(0.1)
    self.assertEqual(resp[0]['error']['code'], 4242)
    self.assertEqual(resp[0]['error']['value'], "Test Toto Exception")
  
  def test_add_connection(self):
    self.worker.add_connection(self.worker_addresses[1])
    sleep(0.1)
    self.assertTrue(self.worker_addresses[0] in self.worker.active_connections)
    self.assertTrue(self.worker_addresses[1] in self.worker.active_connections)
    self.worker.add_connection(self.worker_addresses[2])
    sleep(0.1)
    self.assertTrue(self.worker_addresses[0] in self.worker.active_connections)
    self.assertTrue(self.worker_addresses[1] in self.worker.active_connections)
    self.assertTrue(self.worker_addresses[2] in self.worker.active_connections)

    self.worker.set_connections(self.worker_addresses[:1])
    sleep(0.1)
    self.assertTrue(self.worker_addresses[0] in self.worker.active_connections)
    self.assertTrue(self.worker_addresses[1] not in self.worker.active_connections)
    self.assertTrue(self.worker_addresses[2] not in self.worker.active_connections)
    self.worker.set_connections(self.worker_addresses)
    sleep(0.1)
    self.assertTrue(self.worker_addresses[0] in self.worker.active_connections)
    self.assertTrue(self.worker_addresses[1] in self.worker.active_connections)
    self.assertTrue(self.worker_addresses[2] in self.worker.active_connections)
    self.worker.set_connections(self.worker_addresses[2:])
    sleep(0.1)
    self.assertTrue(self.worker_addresses[0] not in self.worker.active_connections)
    self.assertTrue(self.worker_addresses[1] not in self.worker.active_connections)
    self.assertTrue(self.worker_addresses[2] in self.worker.active_connections)
    self.worker.set_connections(self.worker_addresses[:1])
    sleep(0.1)
    self.assertTrue(self.worker_addresses[0] in self.worker.active_connections)
    self.assertTrue(self.worker_addresses[1] not in self.worker.active_connections)
    self.assertTrue(self.worker_addresses[2] not in self.worker.active_connections)

  def test_remove_connection(self):
    self.worker.set_connections(self.worker_addresses)
    sleep(0.1)
    self.assertTrue(self.worker_addresses[0] in self.worker.active_connections)
    self.assertTrue(self.worker_addresses[1] in self.worker.active_connections)
    self.assertTrue(self.worker_addresses[2] in self.worker.active_connections)
    self.worker.remove_connection(self.worker_addresses[1])
    sleep(0.1)
    self.assertTrue(self.worker_addresses[0] in self.worker.active_connections)
    self.assertTrue(self.worker_addresses[1] not in self.worker.active_connections)
    self.assertTrue(self.worker_addresses[2] in self.worker.active_connections)
    self.worker.remove_connection(self.worker_addresses[2])
    sleep(0.1)
    self.assertTrue(self.worker_addresses[0] in self.worker.active_connections)
    self.assertTrue(self.worker_addresses[1] not in self.worker.active_connections)
    self.assertTrue(self.worker_addresses[2] not in self.worker.active_connections)
    
  def test_remote_messaging(self):
    self.worker.set_connections(self.worker_addresses)
    sleep(0.1)
    worker_ids = list()
    for i in xrange(3):
      self.worker.return_pid(callback=lambda response: worker_ids.append(response['pid']))
    while len(worker_ids) < 3:
      sleep(0.1)
    self.assertEqual(len(set(worker_ids)), 3)
    self.worker.set_connections(self.worker_addresses[:1])
    sleep(0.1)
    worker_ids = list()
    for i in xrange(3):
      self.worker.return_pid(callback=lambda response: worker_ids.append(response['pid']))
    while len(worker_ids) < 3:
      sleep(0.1)
    self.assertEqual(len(set(worker_ids)), 1)
    
  def test_worker_routing(self):
    self.worker.set_connections(self.worker_addresses)
    sleep(0.1)
    worker_ids = list()
    for i in xrange(30):
      sleep(0.01)
      self.worker.return_pid(callback=lambda response: worker_ids.append(response['pid']))
    while len(worker_ids) < 30:
      sleep(0.1)
    self.worker.set_connections(self.worker_addresses[:1])
    sleep(0.1)
    order = (worker_ids[0], worker_ids[1], worker_ids[2])
    self.assertEqual(len(set(order)), len(order))
    for i in xrange(3, 3, 30):
      self.assertSquenceEqual(order, worker_ids[i:i+3])

