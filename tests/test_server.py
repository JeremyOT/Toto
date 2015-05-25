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
from toto.handler import TotoHandler
from util import *
import logging

def before_handler(handler, transaction, method):
  logging.info('Begin %s %s' % (method, transaction))

def after_handler(handler, transaction):
  logging.info('Finished %s' % transaction)
TotoHandler.set_before_handler(before_handler)
TotoHandler.set_after_handler(after_handler)

def run_server(processes=1, daemon='start'):
  TotoServer(method_module='web_methods', port=9000, debug=True, processes=processes, daemon=daemon, pidfile='server.pid').run()

class TestWeb(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    print 'Starting server'
    Process(target=run_server, args=[int(os.environ.get('NUM_PROCS', -1))]).start()
    sleep(0.5)

  @classmethod
  def tearDownClass(cls):
    print 'Stopping server'
    Process(target=run_server, args=[int(os.environ.get('NUM_PROCS', -1)), 'stop']).start()
    sleep(0.5)

  def _test_generic(self, method):
    params = {'arg1': 1, 'arg2': 'hello'}
    response = request(method, params)
    self.assertEqual(params, response['parameters'])

  def test_method(self):
    self._test_generic('return_value')

  def test_method_async(self):
    self._test_generic('return_value_async')

  def test_method_coroutine(self):\
    self._test_generic('return_value_coroutine')

  def test_method_task(self):
    self._test_generic('return_value_task')

  def test_method_task_coroutine(self):
    self._test_generic('return_value_task_coroutine')

  def test_no_method(self):
    request = {}
    request['parameters'] = {'arg1': 1, 'arg2': 'hello'}
    headers = {'content-type': 'application/json'}
    req = urllib2.Request('http://127.0.0.1:9000/', json.dumps(request), headers)
    f = urllib2.urlopen(req)
    response = json.loads(f.read())
    self.assertEqual({'error': {'code': 1002, 'value': 'Missing method.'}}, response)

  def test_bad_method(self):
    response = request('bad_method.test', {'arg1': 1, 'arg2': 'hello'}, response_key='error')
    self.assertEqual({'code': 1001, 'value': "Cannot call 'bad_method.test'."}, response)

  def test_method_form_post(self):
    request = {}
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    req = urllib2.Request('http://127.0.0.1:9000/return_value', 'arg1=1&arg2=hello', headers)
    f = urllib2.urlopen(req)
    response = json.loads(f.read())['result']
    self.assertEqual(response['parameters']['arg1'][0], '1')
    self.assertEqual(response['parameters']['arg2'][0], 'hello')

  def test_method_no_params(self):
    request = {}
    request['method'] = 'return_value'
    headers = {'content-type': 'application/json'}
    req = urllib2.Request('http://127.0.0.1:9000/', json.dumps(request), headers)
    f = urllib2.urlopen(req)
    response = json.loads(f.read())['result']
    self.assertEquals(response['parameters'], {'method': 'return_value'})

  def test_url_method(self):
    request = {}
    request['parameters'] = {'arg1': 1, 'arg2': 'hello'}
    headers = {'content-type': 'application/json'}
    req = urllib2.Request('http://127.0.0.1:9000/return_value', json.dumps(request), headers)
    f = urllib2.urlopen(req)
    response = json.loads(f.read())['result']
    self.assertEqual(request['parameters'], response['parameters'])

  def test_get_method(self):
    request = {}
    request['parameters'] = {'arg1': '1', 'arg2': 'hello'}
    req = urllib2.Request('http://127.0.0.1:9000/return_value?arg1=1&arg2=hello')
    f = urllib2.urlopen(req)
    response = json.loads(f.read())['result']
    self.assertEqual(request['parameters'], response['parameters'])

  def test_batch_method(self):
    batch = {}
    headers = {'content-type': 'application/json'}
    for i in xrange(3):
      rid = uuid4().hex
      request = {}
      request['method'] = 'return_value'
      request['parameters'] = {'arg1': 1, 'arg2': rid}
      batch[rid] = request
    req = urllib2.Request('http://127.0.0.1:9000/', json.dumps({'batch': batch}), headers)
    f = urllib2.urlopen(req)
    batch_response = json.loads(f.read())['batch']
    for rid, response in batch_response.iteritems():
      request['parameters']['arg2'] = rid
      self.assertEqual(request['parameters'], response['result']['parameters'])

  def test_batch_method_async(self):
    batch = {}
    headers = {'content-type': 'application/json'}
    for i in xrange(3):
      rid = uuid4().hex
      request = {}
      request['method'] = 'return_value_async'
      request['parameters'] = {'arg1': 1, 'arg2': rid}
      batch[rid] = request
    req = urllib2.Request('http://127.0.0.1:9000/', json.dumps({'batch': batch}), headers)
    f = urllib2.urlopen(req)
    batch_response = json.loads(f.read())['batch']
    for rid, response in batch_response.iteritems():
      request['parameters']['arg2'] = rid
      self.assertEqual(request['parameters'], response['result']['parameters'])

  def test_batch_method_task(self):
    batch = {}
    headers = {'content-type': 'application/json'}
    for i in xrange(3):
      rid = uuid4().hex
      request = {}
      request['method'] = 'return_value_task'
      request['parameters'] = {'arg1': 1, 'arg2': rid}
      batch[rid] = request
    req = urllib2.Request('http://127.0.0.1:9000/', json.dumps({'batch': batch}), headers)
    f = urllib2.urlopen(req)
    batch_response = json.loads(f.read())['batch']
    for rid, response in batch_response.iteritems():
      request['parameters']['arg2'] = rid
      self.assertEqual(request['parameters'], response['result']['parameters'])

  def test_exception(self):
    response = request('throw_exception', {'arg1': 1, 'arg2': 'hello'}, response_key='error')
    self.assertEqual({'code': 1000, 'value': "Test Exception"}, response)

  def test_toto_exception(self):
    response = request('throw_toto_exception', {'arg1': 1, 'arg2': 'hello'}, response_key='error')
    self.assertEqual({'code': 4242, 'value': "Test Toto Exception"}, response)

  def test_toto_exception_async_coroutine(self):
    response = request('throw_toto_exception_async_coroutine', {'arg1': 1, 'arg2': 'hello'}, response_key='error')
    self.assertEqual({'code': 4242, 'value': "Test Toto Exception"}, response)

  def test_toto_exception_task_coroutine(self):
    response = request('throw_toto_exception_task_coroutine', {'arg1': 1, 'arg2': 'hello'}, response_key='error')
    self.assertEqual({'code': 4242, 'value': "Test Toto Exception"}, response)

  def test_exception_async_coroutine(self):
    response = request('throw_exception_async_coroutine', {'arg1': 1, 'arg2': 'hello'}, response_key='error')
    self.assertEqual({'code': 1000, 'value': "Test Exception"}, response)

  def test_exception_task_coroutine(self):
    response = request('throw_exception_task_coroutine', {'arg1': 1, 'arg2': 'hello'}, response_key='error')
    self.assertEqual({'code': 1000, 'value': "Test Exception"}, response)
