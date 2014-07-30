import unittest
import urllib
from toto.session import TotoSession
from toto.clientsessioncache import ClientCache, AESCipher
from Crypto.Cipher import AES
from time import time

class TestClientCache(unittest.TestCase):

  def test_session_storage(self):
    cache = ClientCache(AESCipher('12345678901234561234567890123456'))
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
    url_safe = urllib.quote_plus(session_id)
    self.assertEqual(session_id, url_safe)
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
