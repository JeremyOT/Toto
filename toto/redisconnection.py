import redis
from toto.exceptions import *
from toto.session import *
from time import time
from datetime import datetime
from dbconnection import DBConnection
import base64
import uuid
import hmac
import hashlib
import toto.secret as secret

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
    session_data = self._refresh_cache() or TotoSession.loads(self._db.get(_session_key(self.session_id)))
    self.__init__(self._db, session_data, self._session_cache)
  
  def save(self):
    if not self._verified:
      raise TotoException(ERROR_NOT_AUTHORIZED, "Not authorized")
    if not self._save_cache():
      self._db.setex(_session_key(self.session_id), int(self.expires - time()), TotoSession.dumps(self.session_data()))

class RedisConnection(DBConnection):
  
  def __init__(self, host='localhost', port=6379, database=0, session_ttl=24*60*60*365, anon_session_ttl=24*60*60, session_renew=0, anon_session_renew=0):
    self.db = redis.StrictRedis(host=host, port=port, db=database)
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

  def _load_uncached_data(self, session_id):
    data = self.db.get(_session_key(session_id))
    if data:
      return TotoSession.loads(data)
    return None

  def create_session(self, user_id=None, password=None, verify_password=True):
    user_id = user_id.lower()
    if not user_id:
      user_id = ''
    account_key = _account_key(user_id)
    account = user_id and password and self.db.hmget(account_key, 'user_id', 'password')
    if user_id and (account[0] != user_id or (verify_password and not secret.verify_password(password, account[1]))):
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID or password")
    session_id = RedisSession.generate_id()
    ttl = (user_id and self.session_ttl or self.anon_session_ttl)
    expires = time() + ttl
    session_key = _session_key(session_id)
    session_data = {'user_id': user_id, 'expires': expires, 'session_id': session_id}
    if not self._cache_session_data(session_data):
      self.db.setex(session_key, int(ttl), TotoSession.dumps(session_data))
    session = RedisSession(self.db, session_data, self._session_cache)
    session._verified = True
    return session

  def retrieve_session(self, session_id, hmac_data=None, data=None):
    session_key = _session_key(session_id)
    session_data = self._load_session_data(session_id)
    if not session_data:
      return None
    user_id = session_data['user_id']
    if user_id and data and hmac_data != base64.b64encode(hmac.new(str(user_id), data, hashlib.sha1).digest()):
      raise TotoException(ERROR_INVALID_HMAC, "Invalid HMAC")
    ttl = user_id and self.session_renew or self.anon_session_renew
    if session_data['expires'] < (time() + ttl):
      session_data['expires'] = time() + ttl
      if not self._cache_session_data(session_data):
        self.db.setex(session_key, int(ttl), TotoSession.dumps(session_data))
    session = RedisSession(self.db, session_data, self._session_cache)
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

class RedisSessionCache(TotoSessionCache):

  def __init__(self, db):
    '''``db`` must be an instance of ``redis.StrictRedis`` initialized to the target database.
    '''
    self.db = db

  def store_session(self, session_data):
    session_key = _session_key(session_data['session_id'])
    self.db.setex(session_key, int(session_data['expires'] - time()), TotoSession.dumps(session_data))

  def load_session(self, session_id):
    session_key = _session_key(session_id)
    session_data = self.db.get(session_key)
    if not session_data:
      return None
    else:
      return TotoSession.loads(session_data)
    
