import redis
from toto.exceptions import *
from toto.session import *
from time import time
from datetime import datetime
from dbconnection import DBConnection
import base64
import uuid

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
    if not self._save_cache():
      self._db.setex(_session_key(self.session_id), int(self.expires - time()), TotoSession.dumps(self.session_data()))

class RedisConnection(DBConnection):

  def __init__(self, host='localhost', port=6379, database=0):
    super(RedisConnection, self).__init__(*args, **kwargs)
    self.db = redis.StrictRedis(host=host, port=port, db=database)

  def _store_session(self, session_id, session_data):
    session_key = _session_key(session_id)
    self.db.setex(session_key, int(float(session_data['expires']) - time()), TotoSession.dumps(session_data))

  def _update_password(self, user_id, account, hashed_password):
    account_key = _account_key(user_id)
    self.db.hset(account_key, 'password', hashed_password)

  def _instantiate_session(self, session_data, session_cache):
    return RedisSession(self.db, session_data, self._session_cache)

  def _get_account(self, user_id):
    return self.db.hmget(account_key, 'user_id', 'password')

  def _store_account(self, user_id, values):
    account_key = _account_key(user_id)
    self.db.hmset(account_key, values)

  def _load_uncached_data(self, session_id):
    data = self.db.get(_session_key(session_id))
    if data:
      return TotoSession.loads(data)
    return None

  def _remove_session(self, session_id):
    session_key = _session_key(session_id)
    self.db.delete(session_key)

class RedisSessionCache(TotoSessionCache):
  '''A ``TotoSessionCache`` implementation that uses Redis for session storage. Useful for improving the speed
  of authenticated requests while still allowing account data to live in e.g. MySQL.

  ``db`` must be an instance of ``redis.StrictRedis`` initialized to the target database.
  '''

  def __init__(self, db):
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

  def remove_session(self, session_id):
    session_key = _session_key(session_id)
    self.db.delete(session_key)
