from toto.exceptions import *
from toto.session import *
from time import time, mktime
from datetime import datetime
from dbconnection import DBConnection
import json

class JSONSession(TotoSession):
  _account = None

  class JSONAccount(TotoAccount):

    def __init__(self, session):
      super(JSONSession.JSONAccount, self).__init__(session)

    def _load_property(self, *args):
      return self._session._db.get('account', self._session.user_id, 'properties')

    def _save_property(self, *args):
      self._session._db.set('account', self._session.user_id, 'properties', self._properties)

    def __setitem__(self, key, value):
      if key != 'account_id':
        super(JSONSession.JSONAccount, self).__setitem__(key, value)

  def __init__(self, db, session_data, session_cache=None):
    super(JSONSession, self).__init__(db, session_data, session_cache)

  def get_account(self):
    if not self._account:
      self._account = JSONSession.JSONAccount(self)
    return self._account

  def session_data(self):
   return {'user_id': self.user_id, 'expires': self.expires, 'session_id': self.session_id, 'state': TotoSession.dumps(self.state)}

  def refresh(self):
    session_data = self._refresh_cache() or self._db.get("session", self.session_id)
    self.__init__(self._db, session_data, self._session_cache)

  def save(self):
    if not self._save_cache():
      self._db.set('session', self.session_id, self.session_data())

class JSONConnection(DBConnection):
  '''A JSON based implementation of DBConnection. Used for debugging. and not
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

  def __init__(self, filename=None, persistent=False, *args, **kwargs):
    super(JSONConnection, self).__init__(*args, **kwargs)
    self._file = filename
    self._persistent = self._file and persistent
    self.db = None
    if self._file:
      with open(self._file, 'rb') as f:
        self._data = json.load(f)
    else:
      self._data = {}

  def _store_account(self, user_id, values):
    self.set('account', user_id, values)

  def _store_session(self, session_id, session_data):
    self.set('session', session_id, session_data)

  def _instantiate_session(self, session_data, session_cache):
    return JSONSession(self, session_data, session_cache)

  def remove_session(self, session_id):
    self.set('session', session_id, None)

  def _load_uncached_data(self, session_id):
    return self._get_key('session', session_id)

  def _get_account(self, user_id):
    account = self.get('account', user_id)
    if not account:
      return None
    return {'password': account['password']}

  def _update_password(self, user_id, hashed_password):
    self.set('account', user_id, 'password', hashed_password)

  def clear(self):
    if self._persistent:
      return
    self._data = {}
