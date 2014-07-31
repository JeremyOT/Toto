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
  db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'db.json')
  print db_file
  TotoServer(method_module='web_methods', port=9000, debug=True, processes=processes, daemon=daemon, pidfile='server.pid', database='json', db_host='').run()

class TestWeb(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    print 'Starting server'
    Process(target=run_server, args=[1]).start()
    sleep(0.5)

  @classmethod
  def tearDownClass(cls):
    print 'Stopping server'
    Process(target=run_server, args=[1, 'stop']).start()
    sleep(0.5)

  def test_create(self):
    test_user = 'test'+uuid4().hex
    r = request('account.create', {'user_id': test_user, 'password': 'test'})
    session_id = r['session_id']
    r = authenticated_request('verify_session', {}, session_id)
    self.assertEqual(r['user_id'], test_user)

  def test_login(self):
    test_user = 'test'+uuid4().hex
    r = request('account.create', {'user_id': test_user, 'password': 'test'})
    session_id1 = r['session_id']
    r = request('account.login', {'user_id': test_user, 'password': 'test'})
    session_id = r['session_id']
    self.assertNotEqual(session_id1, session_id)
    r = authenticated_request('verify_session', {}, session_id)
    self.assertEqual(r['user_id'], test_user)

  def test_bad_login(self):
    test_user = 'test'+uuid4().hex
    r = request('account.login', {'user_id': test_user, 'password': 'test'}, response_key='error')
    self.assertEqual(r, {u'code': 1005, u'value': u'Invalid user ID or password'})
