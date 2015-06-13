import pymongo
from toto.exceptions import *
from toto.session import *
from time import time
from datetime import datetime
import base64
import uuid
import hmac
import hashlib
import toto.secret as secret
from dbconnection import DBConnection

class MongoDBSession(TotoSession):
  _account = None

  class MongoDBAccount(TotoAccount):
    def _load_property(self, *args):
      return self._session._db.accounts.find_one({'user_id': self._session.user_id}, {a: 1 for a in args})

    def _save_property(self, *args):
      self._session._db.accounts.update({'user_id': self._session.user_id}, {'$set': {k: self[k] for k in args}})

  def get_account(self):
    if not self._account:
      self._account = MongoDBSession.MongoDBAccount(self)
    return self._account

  def refresh(self):
    session_data = self._refresh_cache() or self._db.sessions.find_one({'session_id': self.session_id})
    self.__init__(self._db, session_data, self._session_cache)

  def save(self):
    if not self._save_cache():
      self._db.sessions.update({'session_id': self.session_id}, {'$set': {'state': TotoSession.dumps(self.state)}})

class MongoDBConnection(DBConnection):

  def _ensure_indexes(self):
    session_indexes = self.db.sessions.index_information()
    if not 'session_id' in session_indexes:
      self.db.sessions.ensure_index('session_id', unique=True, name='session_id')
    if not 'user_id' in session_indexes:
      self.db.sessions.ensure_index('user_id', name='user_id')
    if not 'expires' in session_indexes:
      self.db.sessions.ensure_index('expires', name='expires')
    account_indexes = self.db.accounts.index_information()
    if not 'user_id' in account_indexes:
      self.db.accounts.ensure_index('user_id', name='user_id')

  def __init__(self, host, port, database, session_ttl=24*60*60*365, anon_session_ttl=24*60*60, session_renew=0, anon_session_renew=0):
    self.db = pymongo.Connection(host, port)[database]
    self._ensure_indexes()
    self.session_ttl = session_ttl
    self.anon_session_ttl = anon_session_ttl or self.session_ttl
    self.session_renew = session_renew or self.session_ttl
    self.anon_session_renew = anon_session_renew or self.anon_session_ttl

  def create_account(self, user_id, password, additional_values={}, **values):
    if not user_id:
      raise TotoException(ERROR_INVALID_USER_ID, "Invalid user ID.")
    if self.db.accounts.find_one({'user_id': user_id}):
      raise TotoException(ERROR_USER_ID_EXISTS, "User ID already in use.")
    values.update(additional_values)
    values['user_id'] = user_id
    values['password'] = secret.password_hash(password)
    self.db.accounts.insert(values)

  def _load_uncached_data(self, session_id):
    return self.db.sessions.find_one({'session_id': session_id, 'expires': {'$gt': time()}})

  def create_session(self, user_id=None, password=None, verify_password=True):
    if not user_id:
      user_id = ''
    account = user_id and self.db.accounts.find_one({'user_id': user_id})
    if user_id and (not account or (verify_password and not secret.verify_password(password, account['password']))):
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID or password")
    session_id = MongoDBSession.generate_id()
    expires = time() + (user_id and self.session_ttl or self.anon_session_ttl)
    session_data = {'user_id': user_id, 'expires': expires, 'session_id': session_id}
    if not self._cache_session_data(session_data):
      self.db.sessions.remove({'user_id': user_id, 'expires': {'$lt': time()}})
      self.db.sessions.insert(session_data)
    session = MongoDBSession(self.db, session_data, self._session_cache)
    return session

  def retrieve_session(self, session_id):
    session_data = self._load_session_data(session_id)
    if not session_data:
      return None
    user_id = session_data['user_id']
    expires = time() + (user_id and self.session_renew or self.anon_session_renew)
    if session_data['expires'] < expires:
      session_data['expires'] = expires
      if not self._cache_session_data(session_data):
        self.db.sesions.update({'session_id': session_id}, {'$set': {'expires': session_data['expires']}})
    session = MongoDBSession(self.db, session_data, self._session_cache)
    return session

  def _remove_session(self, session_id):
    self.db.sessions.remove({'session_id': session_id})

  def clear_sessions(self, user_id):
    self.db.sessions.remove({'user_id': user_id})

  def change_password(self, user_id, password, new_password):
    account = self.db.accounts.find_one({'user_id': user_id})
    if not account or not secret.verify_password(password, account['password']):
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID or password")
    self.db.accounts.update({'user_id': user_id}, {'$set': {'password': secret.password_hash(new_password)}})
    self.clear_sessions(user_id)

  def generate_password(self, user_id):
    account = self.db.accounts.find_one({'user_id': user_id})
    if not account:
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID or password")
    pass_chars = string.ascii_letters + string.digits
    new_password = ''.join([random.choice(pass_chars) for x in xrange(10)])
    self.db.accounts.update({'user_id': user_id}, {'$set': {'password': secret.password_hash(new_password)}})
    self.clear_sessions(user_id)
    return new_password
