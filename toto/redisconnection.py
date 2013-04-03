import redis
from toto.exceptions import *
from toto.session import *
from time import time
from datetime import datetime
import base64
import uuid
import hmac
import hashlib
import cPickle as pickle
import toto.secret as secret
from dbconnection import DBConnection

def _account_key(user_id):
  return 'account:%s' % user_id

def _session_key(session_id):
  return 'session:%s' % session_id

class RedisSession(TotoSession):
  _account = None

  class RedisAccount(TotoAccount):
    def _load_property(self, *args):
      return dict(zip(args, self._session._db.hmget(_account_key(self._session.user_id), args)))

    def _save_property(self, *args):
      self._session._db.hmset(_account_key(self._session.user_id), {k: self[k] for k in args})

  def get_account(self):
    if not self._account:
      self._account = RedisSession.RedisAccount(self)
    return self._account

  def refresh(self):
    session_data = self._db.hgetall(_session_key(self.session_id))
    self.__init__(self._db, session_data)
  
  def save(self):
    if not self._verified:
      raise TotoException(ERROR_NOT_AUTHORIZED, "Not authorized")
    self._db.hset(_session_key(self.session_id), 'state', pickle.dumps(self.state))

class RedisConnection(DBConnection):
  
  def __init__(self, host='localhost', port=6379, database=0, session_ttl=24*60*60*365, anon_session_ttl=24*60*60, session_renew=0, anon_session_renew=0):
    self.db = redis.Redis(host=host, port=port, db=database)
    self.session_ttl = session_ttl
    self.anon_session_ttl = anon_session_ttl or self.session_ttl
    self.session_renew = session_renew or self.session_ttl
    self.anon_session_renew = anon_session_renew or self.anon_session_ttl

  def create_account(self, user_id, password, additional_values={}, **values):
    if not user_id:
      raise TotoException(ERROR_INVALID_USER_ID, "Invalid user ID.")
    user_id = user_id.lower()
    account_key = _account_key(user_id)
    if self.db.exists(account_key):
      raise TotoException(ERROR_USER_ID_EXISTS, "User ID already in use.")
    values.update(additional_values)
    values['user_id'] = user_id
    values['password'] = secret.password_hash(password)
    self.db.hmset(account_key, values)

  def create_session(self, user_id=None, password=None, verify_password=True):
    user_id = user_id.lower()
    if not user_id:
      user_id = ''
    account_key = _account_key(user_id)
    account = user_id and password and self.db.hmget(account_key, 'user_id', 'password')
    if user_id and (account[0] != user_id or (verify_password and not secret.verify_password(password, account[1]))):
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID or password")
    session_id = base64.b64encode(uuid.uuid4().bytes, '-_')[:-2]
    ttl = (user_id and self.session_ttl or self.anon_session_ttl)
    expires = time() + ttl
    session_key = _session_key(session_id)
    self.db.hmset(session_key, {'user_id': user_id, 'expires': expires, 'session_id': session_id})
    self.db.expire(session_key, ttl)
    session = RedisSession(self.db, {'user_id': user_id, 'expires': expires, 'session_id': session_id})
    session._verified = True
    return session

  def retrieve_session(self, session_id, hmac_data=None, data=None):
    session_key = _session_key(session_id)
    session_data = self.db.hgetall(session_key)
    if not session_data:
      return None
    user_id = session_data['user_id']
    ttl = (user_id and self.session_ttl or self.anon_session_ttl)
    session_data['expires'] = time() + ttl
    self.db.expire(session_key, ttl)
    session = RedisSession(self.db, session_data)
    if data and hmac_data != base64.b64encode(hmac.new(str(user_id), data, hashlib.sha1).digest()):
      raise TotoException(ERROR_INVALID_HMAC, "Invalid HMAC")
    session._verified = True
    return session

  def remove_session(self, session_id):
    session_key = _session_key(session_id)
    self.db.delete(session_key)

  def clear_sessions(self, user_id):
    pass

  def change_password(self, user_id, password, new_password):
    user_id = user_id.lower()
    account_key = _account_key(user_id)
    account = self.db.hmget(account_key, 'user_id', 'password')
    if account[0] != user_id or not secret.verify_password(password, account[1]):
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID or password")
    self.db.hset(account_key, 'password', secret.password_hash(new_password))

  def generate_password(self, user_id):
    user_id = user_id.lower()
    account_key = _account_key(user_id)
    if self.db.hget(account_key, 'user_id') != user_id:
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID or password")
    pass_chars = string.ascii_letters + string.digits 
    new_password = ''.join([random.choice(pass_chars) for x in xrange(10)])
    self.db.hset(account_key, 'password', secret.password_hash(new_password))
    return new_password
