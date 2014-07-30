import unittest
import urllib2
import urllib
import urlparse
import json
import os
import signal
import cPickle as pickle
from uuid import uuid4
from toto.secret import *
from multiprocessing import Process, active_children
from toto.session import TotoSession, SESSION_ID_LENGTH
from time import sleep, time

class TestSession(unittest.TestCase):

  def test_generate_id(self):
    session_id = TotoSession.generate_id()
    self.assertEqual(len(session_id), SESSION_ID_LENGTH)
    url_safe = urllib.quote_plus(session_id)
    self.assertEqual(session_id, url_safe)

  def test_data_storage(self):
    user_id = 'test@toto.li'
    expires = time() + 1000.0
    session_id = TotoSession.generate_id()
    session_data = {'session_id': session_id, 'expires': expires, 'user_id': user_id}
    session = TotoSession(None, session_data)
    self.assertEqual(session.session_id, session_id)
    self.assertEqual(session.user_id, user_id)
    self.assertEqual(session.expires, expires)
    session['int'] = 1268935
    session['float'] = 92385.03
    session['str'] = 'some test'
    self.assertEqual(session['int'], 1268935)
    self.assertEqual(session['float'], 92385.03)
    self.assertEqual(session['str'], 'some test')

  def test_clone(self):
    user_id = 'test@toto.li'
    expires = time() + 1000.0
    session_id = TotoSession.generate_id()
    session_data = {'session_id': session_id, 'expires': expires, 'user_id': user_id}
    session = TotoSession(None, session_data)
    session['int'] = 1268935
    session['float'] = 92385.03
    session['str'] = 'some test'
    new_session = TotoSession(None, session.session_data())
    self.assertEqual(new_session.session_id, session_id)
    self.assertEqual(new_session.user_id, user_id)
    self.assertEqual(new_session.expires, expires)
    self.assertEqual(new_session['int'], 1268935)
    self.assertEqual(new_session['float'], 92385.03)
    self.assertEqual(new_session['str'], 'some test')

  def test_serialization(self):
    user_id = 'test@toto.li'
    expires = time() + 1000.0
    session_id = TotoSession.generate_id()
    session_data = {'session_id': session_id, 'expires': expires, 'user_id': user_id}
    session = TotoSession(None, session_data)
    session['int'] = 1268935
    session['float'] = 92385.03
    session['str'] = 'some test'
    data = TotoSession.dumps(session.session_data())
    new_session = TotoSession(None, TotoSession.loads(data))
    self.assertEqual(new_session.session_id, session_id)
    self.assertEqual(new_session.user_id, user_id)
    self.assertEqual(new_session.expires, expires)
    self.assertEqual(new_session['int'], 1268935)
    self.assertEqual(new_session['float'], 92385.03)
    self.assertEqual(new_session['str'], 'some test')

  def test_set_serializer(self):
    session = {'session_id': TotoSession.generate_id(), 'expires': time() + 1000.0, 'user_id': 'test@toto.li'}
    TotoSession.set_serializer(pickle)
    pickle_serialized = TotoSession.dumps(session)
    self.assertTrue(isinstance(pickle_serialized, str))
    TotoSession.set_serializer(json)
    json_serialized = TotoSession.dumps(session)
    self.assertTrue(isinstance(json_serialized, str))
    self.assertNotEqual(pickle_serialized, json_serialized)
    TotoSession.set_serializer(pickle)
    self.assertEqual(TotoSession.loads(pickle_serialized), session)
    TotoSession.set_serializer(json)
    self.assertEqual(TotoSession.loads(json_serialized), session)
