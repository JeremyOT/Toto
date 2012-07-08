import pycassa
from pycassa import *
from pycassa.types import *
from toto.exceptions import *
from toto.session import *
from time import time
from datetime import datetime
from uuid import uuid4
import base64
import uuid
import hmac
import hashlib
import cPickle as pickle
import pycassa_util

class CassandraSession(TotoSession):
  _account = None

  class CassandraAccount(TotoAccount):
    def _load_property(self, *args):
      return dict(self._session._db.accounts.get_columns(self._session.user_id, columns=args))

    def _save_property(self, *args):
      self._session._db.accounts.insert(self._session.user_id, dict([(k, self[k]) for k in args]))

  def get_account(self):
    if not self._account:
      self._account = CassandraSession.CassandraAccount(self)
    return self._account

  def refresh(self):
    session_data = self._db.sessions.get(self.session_id)
    self.__init__(self._db, session_data)
  
  def save(self):
    if not self._verified:
      raise TotoException(ERROR_NOT_AUTHORIZED, "Not authorized")
    self._db.insert(self.session_id, {'expires': self.expires, 'user_id': self.user_id, 'state': pickle.dumps(self.state)}, ttl=(self.expires-time()))

class CassandraDB():
  def __init__(self, pool):
    self.pool = pool
    self.column_families = {}

  def __get__(self, name):
    try:
      return self.column_families[name]
    except:
      self.column_families[name] = ColumnFamily(self.pool, name)
      return self.column_families[name]

class CassandraConnection():

  def _create_column_families(self):
    from pycassa.system_manager import SystemManager
    sysm = SystemManager(server=self.hosts[0])
    families = sysm.get_keyspace_column_families(self.keyspace, True)
    if 'accounts' not in families:
      sysm.create_column_family(self.keyspace, 'accounts', key_validation_class=LexicalUUIDType(), comparator_type=UTF8Type(), default_validation_class=BytesType())
      sysm.create_index(self.keyspace, 'sessions', 'user_id', UTF8Type(), index_name='account_user_id')
    if 'sessions' not in families:
      column_types = {'user_id': LexicalUUIDType(), 'expires': DoubleType()}
      sysm.create_column_family(self.keyspace, 'sessions', key_validation_class=LexicalUUIDType(), comparator_type=UTF8Type(), default_validation_class=BytesType(), column_validation_classes=column_types)
      sysm.create_index(self.keyspace, 'sessions', 'user_id', LEXICAL_UUID_TYPE, index_name='session_user_id')
    sysm.close()
  
  def __init__(self, hosts, keyspace, password_salt='toto', session_ttl=24*60*60*365, anon_session_ttl=24*60*60, session_renew=0, anon_session_renew=0):
    self.db = CassandraDB(ConnectionPool(keyspace, hosts))
    self.keyspace = keyspace
    self.hosts = hosts
    self._create_column_families()
    self.password_salt = password_salt
    self.session_ttl = session_ttl
    self.anon_session_ttl = anon_session_ttl or self.session_ttl
    self.session_renew = session_renew or self.session_ttl
    self.anon_session_renew = anon_session_renew or self.anon_session_ttl

  def password_hash(self, user_id, password):
    return hashlib.sha256(user_id + self.password_salt + password).hexdigest()

  def create_account(self, user_id, password, additional_values={}, **values):
    user_id = user_id.lower()
    try:
      self.db.accounts.get(user_id):
    except:
      raise TotoException(ERROR_USER_ID_EXISTS, "User ID already in use.")
    values.update(additional_values)
    values['user_id'] = user_id
    values['password'] = self.password_hash(user_id, password)
    uid = uuid4()
    self.db.accounts.insert(uid, values)
    return uid

  def create_session(self, user_id=None, password=None):
    if not user_id:
      user_id = ''
    user_id = user_id.lower()
    account = user_id and password and self.db.accounts.find_one({'user_id': user_id, 'password': self.password_hash(user_id, password)})
    if user_id and not account:
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID or password")
    session_id = base64.b64encode(uuid.uuid4().bytes, '-_')[:-2]
    #self.db.sessions.remove({'user_id': user_id, 'expires': {'$lt': time()}})
    expires = time() + (user_id and self.session_ttl or self.anon_session_ttl)
    self.db.sessions.insert({'user_id': user_id, 'expires': expires, 'session_id': session_id})
    session = CassandraSession(self.db, {'user_id': user_id, 'expires': expires, 'session_id': session_id}, expires)
    session._verified = True
    return session

  def retrieve_session(self, session_id, hmac_data, data):
    session_data = self.db.sessions.find_one({'session_id': session_id, 'expires': {'$gt': time()}})
    if not session_data:
      return None
    user_id = session_data['user_id']
    if session_data['expires'] < (time() + (user_id and self.session_renew or self.anon_session_renew)):
      session_data['expires'] = time() + (user_id and self.session_ttl or self.anon_session_ttl)
      self.db.sesions.update({'session_id': session_id}, {'$set': {'expires': session_data['expires']}})
    session = CassandraSession(self.db, session_data)
    if data and hmac_data != base64.b64encode(hmac.new(str(user_id), data, hashlib.sha1).digest()):
      raise TotoException(ERROR_INVALID_HMAC, "Invalid HMAC")
    session._verified = True
    return session

  def remove_session(self, session_id):
    self.db.sessions.remove({'session_id': session_id})

  def clear_sessions(self, user_id):
    user_id = user_id.lower()
    self.db.sessions.remove({'user_id': user_id})

  def change_password(self, user_id, password, new_password):
    user_id = user_id.lower()
    account = self.db.accounts.find_one({'user_id': user_id, 'password': self.password_hash(user_id, password)})
    if not account:
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID or password")
    self.db.accounts.update({'user_id': user_id, 'password': self.password_hash(user_id, password)}, {'$set': {'password': self.password_hash(user_id, new_password)}})
    self.clear_sessions(user_id)

  def generate_password(self, user_id):
    user_id = user_id.lower()
    account = self.db.accounts.find_one({'user_id': user_id})
    if not account:
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID or password")
    pass_chars = string.ascii_letters + string.digits 
    new_password = ''.join([random.choice(pass_chars) for x in xrange(10)])
    self.db.accounts.update({'user_id': user_id}, {'$set': {'password': self.password_hash(user_id, new_password)}})
    self.clear_sessions(user_id)
    return new_password
