from toto.exceptions import *
from toto.session import *
from time import time, mktime
from datetime import datetime
from dbconnection import DBConnection
from uuid import uuid4
import toto.secret as secret
import uuid
import random
import string
import json

class FileSession(TotoSession):
  _account = None

  class FileAccount(TotoAccount):

    def __init__(self, session):
      super(FileSession.FileAccount, self).__init__(session)

    def _load_property(self, *args):
      return self._session._db.get('account', self._session.user_id, 'properties')

    def _save_property(self, *args):
      self._session._db.set('account', self._session.user_id, 'properties', self._properties)

    def __setitem__(self, key, value):
      if key != 'account_id':
        super(FileSession.FileAccount, self).__setitem__(key, value)

  def __init__(self, db, session_data, session_cache=None):
    super(FileSession, self).__init__(db, session_data, session_cache)

  def get_account(self):
    if not self._account:
      self._account = FileSession.FileAccount(self)
    return self._account

  def session_data(self):
   return {'user_id': self.user_id, 'expires': self.expires, 'session_id': self.session_id, 'state': TotoSession.dumps(self.state)}

  def refresh(self):
    session_data = self._refresh_cache() or self._db.get("session", self.session_id)
    self.__init__(self._db, session_data, self._session_cache)

  def save(self):
    if not self._verified:
      raise TotoException(ERROR_NOT_AUTHORIZED, "Not authorized")
    if not self._save_cache():
      self._db.set('session', self.session_id, self.session_data())

class FileConnection(DBConnection):
  '''A file based implementation of DBConnection. Used for debugging. and not
  recommended for production use. This class is not thread safe.

  Data is loaded from the specified ``filename`` and if ``persistent`` is set
  to ``True``, each change will overwrite the file with the current data.
  '''

  def _get_key(self, *args, **kwargs):
    data = self._data
    for k in args:
      if k not in data:
        if kwargs.get('create'):
          data[k] = {}
        else:
          return None
      data = data[k]
    return data

  def _set_dict(self, d, k, v):
    if v is not None:
      d[k] = v
    else:
      d.pop(k, None)

  def set(self, *args, **kwargs):
    '''Updates the dictionary in one of two ways. If ``kwargs`` are provided, the
    dictionary at the path provided by unrolling ``args`` is updated with the
    values from ``kwargs``. Otherwise the path provided by unrolling ``args[:-1]``
    is set to ``args[-1]``.
    '''
    if kwargs:
      path = args
    else:
      path = args[:-2]
    data = self._get_key(*path, create=True)
    if kwargs:
      for k, v in kwargs.iteritems():
        self._set_dict(data, k ,v)
    else:
      self._set_dict(data, args[-2], args[-1])
    if self._persistent:
      with open(self._file, 'wb') as f:
        json.dump(self._data, f)

  def get(self, *args):
    '''Returns the object at the path provided by unrolling ``args``.
    '''
    d = self._get_key(*args[:-1])
    return d and d.get(args[-1])

  def __init__(self, filename=None, persistent=False, session_ttl=24*60*60*365, anon_session_ttl=24*60*60, session_renew=0, anon_session_renew=0):
    self._file = filename
    self._persistent = self._file and persistent
    self.db = None
    if self._file:
      with open(self._file, 'rb') as f:
        self._data = json.load(f)
    else:
      self._data = {}
    self.session_ttl = session_ttl
    self.anon_session_ttl = anon_session_ttl or self.session_ttl
    self.session_renew = session_renew or self.session_ttl
    self.anon_session_renew = anon_session_renew or self.anon_session_ttl

  def create_account(self, user_id, password, additional_values={}, **values):
    if not user_id:
      raise TotoException(ERROR_INVALID_USER_ID, "Invalid user ID.")
    user_id = user_id.lower()
    if self.get("account", user_id):
      raise TotoException(ERROR_USER_ID_EXISTS, "User ID already in use.")
    values.update(additional_values)
    values['user_id'] = user_id
    values['password'] = secret.password_hash(password)
    self.set('account', user_id, values)

  def create_session(self, user_id=None, password=None, verify_password=True, key=None):
    if not user_id:
      user_id = ''
    user_id = user_id.lower()
    account = user_id and self.get("account", user_id)
    if user_id and (not account or (verify_password and not secret.verify_password(password, account['password']))):
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID or password")
    session_id = FileSession.generate_id()
    expires = time() + (user_id and self.session_ttl or self.anon_session_ttl)
    session_data = {'user_id': user_id, 'expires': expires, 'session_id': session_id}
    if key:
      session_data['key'] = key
    if not self._cache_session_data(session_data):
      self.set('session', session_id, session_data)
    session = FileSession(self, session_data, self._session_cache)
    session._verified = True
    return session

  def retrieve_session(self, session_id, hmac_data=None, data=None):
    session_data = self._load_session_data(session_id)
    if not session_data:
      return None
    user_id = session_data['user_id']
    expires = time() + (user_id and self.session_renew or self.anon_session_renew)
    if session_data['expires'] < expires:
      session_data['expires'] = expires
      if not self._cache_session_data(session_data):
        self.set('session', session_id, 'expires', session_data['expires'])
    session = FileSession(self, session_data, self._session_cache)
    return session

  def remove_session(self, session_id):
    self.set('session', session_id, None)

  def change_password(self, user_id, password, new_password):
    user_id = user_id.lower()
    account = user_id and self.get("account", user_id)
    if not account or not secret.verify_password(password, account['password']):
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID or password")
    self.set('account', user_id, 'password', secret.password_hash(new_password))

  def generate_password(self, user_id):
    user_id = user_id.lower()
    account = user_id and self.get("account", user_id)
    if not account:
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID")
    pass_chars = string.ascii_letters + string.digits
    new_password = ''.join([random.choice(pass_chars) for x in xrange(10)])
    self.set('account', user_id, 'password', secret.password_hash(new_password))
    return new_password

  def _load_uncached_data(self, session_id):
    return self._get_key('session', session_id)

  def clear(self):
    if self._persistent:
      return
    self._data = {}
