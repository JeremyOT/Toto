import unittest
import urllib
import urllib2
import json
import os
import signal
import logging
from toto.session import TotoSession
from toto.clientsessioncache import ClientCache, AESCipher
from Crypto.Cipher import AES
from time import time
from uuid import uuid4
from toto.secret import *
from multiprocessing import Process, active_children
from toto.server import TotoServer
from time import sleep, time
from toto.handler import TotoHandler
from util import *

def before_handler(handler, transaction, method):
  logging.info('Begin %s %s' % (method, transaction))

def after_handler(handler, transaction):
  logging.info('Finished %s' % transaction)
TotoHandler.set_before_handler(before_handler)
TotoHandler.set_after_handler(after_handler)

def run_server(processes=1, daemon='start'):
  db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'db.json')
  print db_file
  TotoServer(method_module='web_methods', port=9000, debug=True, processes=processes, daemon=daemon, pidfile='server.pid', database='json', db_host='', hmac_enabled=True, startup_function='web_startup.on_start').run()

class TestClientCache(unittest.TestCase):

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

  def test_session_storage(self):
    cache = ClientCache(AESCipher('12345678901234561234567890123456'), '12345678901234561234567890123456')
    user_id = 'test@toto.li'
    expires = time() + 1000.0
    session_id = TotoSession.generate_id()
    session_data = {'session_id': session_id, 'expires': expires, 'user_id': user_id}
    session = TotoSession(None, session_data)
    session.session_id = session_id
    self.assertEqual(session.session_id, session_id)
    self.assertEqual(session.user_id, user_id)
    self.assertEqual(session.expires, expires)
    session['int'] = 1268935
    session['float'] = 92385.03
    session['str'] = 'some test'
    session_data = session.session_data()
    session_id = cache.store_session(session_data)
    new_session_data = cache.load_session(session_id)
    new_session = TotoSession(None, new_session_data)
    del session_data['session_id']
    del new_session_data['session_id']
    self.assertEquals(new_session_data, session_data)
    self.assertEqual(new_session.session_id, session_id)
    self.assertEqual(new_session['int'], 1268935)
    self.assertEqual(new_session['float'], 92385.03)
    self.assertEqual(new_session['str'], 'some test')
    self.assertEqual(new_session.user_id, user_id)
    self.assertEqual(new_session.expires, expires)

  def test_create(self):
    test_user = 'test'+uuid4().hex
    r = request('account.create', {'user_id': test_user, 'password': 'test'})
    session_id = r['session_id']
    key = r['key']
    r = authenticated_request('verify_session', {}, session_id, key)
    self.assertEqual(r['user_id'], test_user)

  def test_login(self):
    test_user = 'test'+uuid4().hex
    r = request('account.create', {'user_id': test_user, 'password': 'test'})
    session_id1 = r['session_id']
    r = request('account.login', {'user_id': test_user, 'password': 'test'})
    session_id = r['session_id']
    key = r['key']
    self.assertNotEqual(session_id1, session_id)
    r = authenticated_request('verify_session', {}, session_id, key)
    self.assertEqual(r['user_id'], test_user)
