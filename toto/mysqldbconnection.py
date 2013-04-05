from torndb import *
from toto.exceptions import *
from toto.session import *
from time import time, mktime
from datetime import datetime
from dbconnection import DBConnection
from uuid import uuid4
import toto.secret as secret
import base64
import uuid
import hmac
import hashlib
import random
import string
import cPickle as pickle

class MySQLdbSession(TotoSession):
  _account = None

  class MySQLdbAccount(TotoAccount):
    
    def __init__(self, session):
      super(MySQLdbSession.MySQLdbAccount, self).__init__(session)
      self._properties['account_id'] = session.account_id

    def _load_property(self, *args):
      return self._session._db.get('select ' + ', '.join(args) + ' from account where account_id = %s', self._session.account_id)

    def _save_property(self, *args):
      self._session._db.execute('update account set ' + ', '.join(['%s = %%s' % k for k in args]) + ' where account_id = %s', *([self[k] for k in args] + [self._session.account_id,]))

    def __setitem__(self, key, value):
      if key != 'account_id':
        super(MySQLdbSession.MySQLdbAccount, self).__setitem__(key, value)
    
  def __init__(self, db, session_data):
    super(MySQLdbSession, self).__init__(db, session_data)
    self.account_id = session_data['account_id']

  def get_account(self):
    if not self._account:
      self._account = MySQLdbSession.MySQLdbAccount(self)
    return self._account
  
  def refresh(self):
    session_data = self.db.get("select session.session_id, session.expires, session.state, account.user_id, account.account_id from session join account on account.account_id = session.account_id where session.session_id = %s", session_id)
    self.__init__(session_data)

  def save(self):
    if not self._verified:
      raise TotoException(ERROR_NOT_AUTHORIZED, "Not authorized")
    self._db.execute("update session set state = %s where session_id = %s", pickle.dumps(self.state), self.session_id)

class MySQLdbConnection(DBConnection):

  def create_tables(self, database):
    if not self.db.get('''show tables like "account"'''):
      self.db.execute(''.join(['''create table if not exists `account` (''',
        self.uuid_account_id and '''`account_id` binary(16) not null,''' or '''`account_id` int(8) unsigned not null auto_increment,''',
        '''`password` char(48) default null,
        `user_id` varchar(191) not null,
        primary key (`account_id`),
        unique key `user_id_unique` (`user_id`),
        index `user_id_password` (`user_id`, `password`)
      )''']))
    if not self.db.get('''show tables like "session"'''):
      self.db.execute(''.join(['''create table if not exists `session` (
        `session_id` char(32) not null,''',
        self.uuid_account_id and '''`account_id` binary(16) not null,''' or '''`account_id` int(8) unsigned not null,''',
        '''`expires` double not null,
        `state` blob,
        primary key (`session_id`),
        index (`expires`),
        foreign key (`account_id`) references `account`(`account_id`)
      )''']))

  def __init__(self, host, database, username, password, session_ttl=24*60*60*365, anon_session_ttl=24*60*60, session_renew=0, anon_session_renew=0, uuid_account_id=False):
    self.db = Connection(host, database, username, password)
    self.uuid_account_id = uuid_account_id
    self.create_tables(database)
    self.session_ttl = session_ttl
    self.anon_session_ttl = anon_session_ttl or self.session_ttl
    self.session_renew = session_renew or self.session_ttl
    self.anon_session_renew = anon_session_renew or self.anon_session_ttl

  def create_account(self, user_id, password, additional_values={}, **values):
    if not user_id:
      raise TotoException(ERROR_INVALID_USER_ID, "Invalid user ID.")
    user_id = user_id.lower()
    if self.db.get("select account_id from account where user_id = %s", user_id):
      raise TotoException(ERROR_USER_ID_EXISTS, "User ID already in use.")
    additional_values.pop('account_id', None)
    values.update(additional_values)
    values['user_id'] = user_id
    values['password'] = secret.password_hash(password)
    if self.uuid_account_id:
      values['account_id'] = uuid4().bytes
    self.db.execute("insert into account (" + ', '.join([k for k in values]) + ") values (" + ','.join(['%s' for k in values]) + ")", *[values[k] for k in values])

  def create_session(self, user_id=None, password=None, verify_password=True):
    if not user_id:
      user_id = ''
    user_id = user_id.lower()
    account = user_id and self.db.get("select * from account where user_id = %s", user_id)
    if user_id and (not account or (verify_password and not secret.verify_password(password, account['password']))):
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID or password")
    session_id = base64.b64encode(uuid.uuid4().bytes, '-_')[:-2]
    self.db.execute("delete from session where account_id = %s and expires <= %s", account['account_id'], time())
    expires = time() + (user_id and self.session_ttl or self.anon_session_ttl)
    self.db.execute("insert into session (account_id, expires, session_id) values (%s, %s, %s)", account['account_id'], expires, session_id)
    session = MySQLdbSession(self.db, {'user_id': user_id, 'expires': expires, 'session_id': session_id, 'account_id': account['account_id']})
    session._verified = True
    return session

  def retrieve_session(self, session_id, hmac_data=None, data=None):
    session_data = self.db.get("select session.session_id, session.expires, session.state, account.user_id, account.account_id from session join account on account.account_id = session.account_id where session.session_id = %s and session.expires > %s", session_id, time())
    if not session_data:
      return None
    user_id = session_data['user_id']
    if session_data['expires'] < (time() + (user_id and self.session_renew or self.anon_session_renew)):
      session_data['expires'] = time() + (user_id and self.session_ttl or self.anon_session_ttl)
      self.db.execute("update session set expires = %s where session_id = %s", session_data['expires'], session_id)
    session = MySQLdbSession(self.db, session_data)
    if data and hmac_data != base64.b64encode(hmac.new(str(user_id), data, hashlib.sha1).digest()):
      raise TotoException(ERROR_INVALID_HMAC, "Invalid HMAC")
    session._verified = True
    return session

  def remove_session(self, session_id):
    self.db.execute("delete from session where session_id = %s", session_id)

  def clear_sessions(self, user_id):
    user_id = user_id.lower()
    self.db.execute("delete from session using session join account on account.account_id = session.account_id where account.user_id = %s", user_id)

  def change_password(self, user_id, password, new_password):
    user_id = user_id.lower()
    account = self.db.get("select account_id, user_id, password from account where user_id = %s", user_id)
    if not account or not secret.verify_password(password, account['password']):
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID or password")
    self.db.execute("update account set password = %s where account_id = %s", secret.password_hash(new_password), account['account_id'])
    self.clear_sessions(user_id)

  def generate_password(self, user_id):
    user_id = user_id.lower()
    account = self.db.get("select account_id, user_id from account where user_id = %s", user_id)
    if not account:
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID")
    pass_chars = string.ascii_letters + string.digits
    new_password = ''.join([random.choice(pass_chars) for x in xrange(10)])
    self.db.execute("update account set password = %s where account_id = %s", secret.password_hash(new_password), account['account_id'])
    self.clear_sessions(user_id)
    return new_password
