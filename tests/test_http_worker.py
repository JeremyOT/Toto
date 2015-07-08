import unittest
import urllib2
import json
import os
import signal
from uuid import uuid4
from toto.secret import *
from toto.httpworkerconnection import HTTPWorkerConnection
from tornado.gen import coroutine
from tornado.concurrent import Future
from tornado.ioloop import IOLoop
from time import sleep, time
from threading import Thread, local
import tornado.web
import atexit

SERVER_LOOPS = []

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

class TestHandler(tornado.web.RequestHandler):
  def initialize(self, port):
    self.port = port

  def post(self):
    request = json.loads(self.request.body)
    if request['method'] == 'bad_method':
      self.set_status(404)
      self.write({'error': {'code': 1000, 'value': "'module' object has no attribute 'bad_method'"}})
    elif request['method'] == 'throw_exception':
      self.set_status(500)
      self.write({'error': {'code': 1000, 'value': "Test Exception"}})
    elif request['method'] == 'throw_toto_exception':
      self.set_status(500)
      self.write({'error': {'code': 4242, 'value': "Test Toto Exception"}})
    elif request['method'] == 'return_pid':
      self.write({'pid': self.port})
    else:
      self.write({'parameters': request['parameters']})

def run_server(port, daemon='start'):
    application = tornado.web.Application([
        (r"/", TestHandler, {'port': port}),
    ])
    ioloop = IOLoop()
    ioloop.make_current()
    SERVER_LOOPS.append(ioloop)
    application.listen(port)
    ioloop.start()

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
    cls.processes = [Thread(target=run_server, args=[10001 + i]) for i in xrange(3)]
    for p in cls.processes:
      p.daemon = False
      p.start()
    sleep(0.5)
    cls.worker_addresses = ['http://127.0.0.1:%d' % (10001 + i) for i in xrange(3)]
    cls.worker = HTTPWorkerConnection(cls.worker_addresses[0], serialization=json, serialization_mime='application/json')
    cls.worker.enable_traceback_logging()

  @classmethod
  def tearDownClass(cls):
    for l in SERVER_LOOPS:
      l.add_callback(l.stop)
    sleep(0.5)
  
  def test_method(self):
    resp = []
    def cb(response):
      resp.append(response)
    parameters = {'arg1': 1, 'arg2': 'hello'}
    @run_loop
    @coroutine
    def run():
      yield self.worker.invoke('return_value', parameters, callback=cb)
    run()
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
    @run_loop
    @coroutine
    def run():
      yield self.worker.return_value(parameters, callback=cb)
    run()
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
    @run_loop
    @coroutine
    def run():
      yield self.worker.invoke('bad_method', parameters, callback=cb)
    run()
    while not resp:
      sleep(0.1)
    self.assertEqual(resp[0]['error']['code'], 1000)
    self.assertEqual(resp[0]['error']['value'], "'module' object has no attribute 'bad_method'")

  def test_exception(self):
    resp = []
    def cb(response):
      resp.append(response)
    parameters = {'arg1': 1, 'arg2': 'hello'}
    @run_loop
    @coroutine
    def run():
      yield self.worker.invoke('throw_exception', parameters, callback=cb)
    run()
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
    @run_loop
    @coroutine
    def run():
      yield self.worker.invoke('throw_toto_exception', parameters, callback=cb)
    run()
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
      @run_loop
      @coroutine
      def run():
        yield self.worker.return_pid(callback=lambda response: worker_ids.append(response['pid']))
      run()
    while len(worker_ids) < 3:
      sleep(0.1)
    self.assertEqual(len(set(worker_ids)), 3)
    self.worker.set_connections(self.worker_addresses[:1])
    sleep(0.1)
    worker_ids = list()
    for i in xrange(3):
      @run_loop
      @coroutine
      def run():
        yield self.worker.return_pid(callback=lambda response: worker_ids.append(response['pid']))
      run()
    while len(worker_ids) < 3:
      sleep(0.1)
    self.assertEqual(len(set(worker_ids)), 1)
    
  def test_worker_routing(self):
    self.worker.set_connections(self.worker_addresses)
    sleep(0.1)
    worker_ids = list()
    for i in xrange(30):
      sleep(0.01)
      @run_loop
      @coroutine
      def run():
        yield self.worker.return_pid(callback=lambda response: worker_ids.append(response['pid']))
      run()
    while len(worker_ids) < 30:
      sleep(0.1)
    self.worker.set_connections(self.worker_addresses[:1])
    sleep(0.1)
    order = (worker_ids[0], worker_ids[1], worker_ids[2])
    self.assertEqual(len(set(order)), len(order))
    for i in xrange(3, 3, 30):
      self.assertSquenceEqual(order, worker_ids[i:i+3])

