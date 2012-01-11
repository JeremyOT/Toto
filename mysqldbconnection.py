from tornado.database import *
from toto.exceptions import *
from time import time
from datetime import datetime
import base64
import uuid
import cPickle as pickle
import hmac
import hashlib
import random
import string

class MySQLdbSession():
  _verified = False
  user_id = None
  session_id = None
  expires = 0
  state = {}
  __connection = None
  
  def __init__(self, connection, session_data):
    self.__connection = connection
    self.user_id = str(session_data['user_id'])
    self.expires = session_data['expires']
    self.session_id = session_data['session_id']
    self.state = 'state' in session_data and session_data['state'] and pickle.loads(session_data['state']) or {}

  def save_state(self):
    if not self._verified:
      raise TotoException(ERROR_NOT_AUTHORIZED, "Not authorized")
    self.__connection.db.execute("update session set state = %s where session_id = %s", pickle.dumps(self.state), self.session_id)

class MySQLdbConnection():
  password_salt = "toto" 
  default_session_ttl = 24 * 60 * 60

  def __init__(self, host, database, username, password):
    self.db = Connection(host, database, username, password)
    #hack to automatically reconnect
    o_execute = self.db._execute
    def safe_execute(*args, **kargs):
      try:
        return o_execute(*args, **kargs)
      except OperationalError:
        self.reconnect()
        return o_execute(*args, **kargs)
    self.db._execute = safe_execute

  def password_hash(self, user_id, password):
    return hashlib.sha256(user_id + self.password_salt + password).hexdigest()

  def create_account(self, user_id, password, additional_values={}):
    if self.db.get("select account_id from account where user_id = %s", user_id):
      raise TotoException(ERROR_USER_ID_EXISTS, "User ID already in use.")
    values = {}
    values.update(additional_values)
    values['user_id'] = user_id
    values['password'] = self.password_hash(user_id, password)
    self.db.execute("insert into account (" + ', '.join([k for k in values]) + ") values (" + ','.join(['%s' for k in values]) + ")", [values[k] for k in values])

  def create_session(self, user_id, password, ttl=0):
    expires = time() + (ttl or self.default_session_ttl)
    account = self.db.get("select * from account where user_id = %s and password = %s", user_id, self.password_hash(user_id, password))
    if not account:
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID or password")
    session_id = base64.b64encode(uuid.uuid4().bytes)
    self.db.execute("delete from session where account_id = %s and expires <= UTC_TIMESTAMP", account['account_id'])
    self.db.execute("insert into session (account_id, expires, session_id) values (%s, %s, %s)", account['account_id'], datetime.utcfromtimestamp(expires).strftime("%Y%m%d%H%M%S"), session_id)
    session = MySQLdbSession(self, {'user_id': user_id, 'expires': expires, 'session_id': session_id})
    return session

  def retrieve_session(self, session_id, hmac_data, data):
    session_data = self.db.get("select session.session_id, session.expires, session.state, account.user_id from session join account on account.account_id = session.account_id where session.session_id = %s and session.expires > UTC_TIMESTAMP", session_id)
    if not session_data:
      raise TotoException(ERROR_INVALID_SESSION_ID, "Invalid session ID")
    session = MySQLdbSession(self, session_data)
    if not hmac_data or hmac_data != base64.b64encode(hmac.new(str(session_data['user_id']), data, hashlib.sha1).digest()):
      raise TotoException(ERROR_INVALID_HMAC, "Invalid HMAC")
    session._verified = True
    return session

  def clear_sessions(self, user_id):
    self.db.execute("delete from session using session join account on account.account_id = session.account_id where account.user_id = %s", user_id)

  def change_password(self, user_id, password, new_password):
    account = self.db.get("select account_id, user_id, password from account where user_id = %s and password = %s", user_id, self.password_hash(user_id, password))
    if not account:
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID or password")
    self.db.execute("update account set password = %s where account_id = %s", self.password_hash(user_id, new_password), account['account_id'])
    self.clear_sessions(user_id)

  def generate_password(self, user_id):
    account = self.db.get("select account_id, user_id from account where user_id = %s", user_id)
    if not account:
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID")
    pass_chars = string.ascii_letters + string.digits
    new_password = ''.join([random.choice(pass_chars) for x in xrange(10)])
    self.db.execute("update account set password = %s where account_id = %s", self.password_hash(user_id, new_password), account['account_id'])
    self.clear_sessions(user_id)
    return new_password
