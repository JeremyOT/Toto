from torndb import *
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

  def __init__(self, db, session_data, session_cache=None):
    super(MySQLdbSession, self).__init__(db, session_data, session_cache)
    self.account_id = session_data['account_id']

  def get_account(self):
    if not self._account:
      self._account = MySQLdbSession.MySQLdbAccount(self)
    return self._account

  def session_data(self):
   return {'user_id': self.user_id, 'expires': self.expires, 'session_id': self.session_id, 'state': TotoSession.dumps(self.state), 'account_id': self.account_id}

  def refresh(self):
    session_data = self._refresh_cache() or self._db.get("select session.session_id, session.expires, session.state, account.user_id, account.account_id from session join account on account.account_id = session.account_id where session.session_id = %s", session_id)
    self.__init__(self._db, session_data, self._session_cache)

  def save(self):
    if not self._save_cache():
      self._db.execute("update session set state = %s where session_id = %s", TotoSession.dumps(self.state), self.session_id)

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
        `session_id` char(22) not null,''',
        self.uuid_account_id and '''`account_id` binary(16) not null,''' or '''`account_id` int(8) unsigned not null,''',
        '''`expires` double not null,
        `state` blob,
        primary key (`session_id`),
        index (`expires`),
        foreign key (`account_id`) references `account`(`account_id`)
      )''']))

  def __init__(self, host, database, username, password, uuid_account_id=False, pool_size=1, *args, **kwargs):
    super(MySQLdbConnection, self).__init__(*args, **kwargs)
    self.db = Connection(host, database, username, password)
    self.uuid_account_id = uuid_account_id
    self.create_tables(database)

  def _store_account(self, user_id, values):
    if self.uuid_account_id:
      values['account_id'] = uuid4().bytes
    self.db.execute("insert into account (" + ', '.join([k for k in values]) + ") values (" + ','.join(['%s' for k in values]) + ")", *[values[k] for k in values])

  def _load_uncached_data(self, session_id):
    return self.db.get("select session.session_id, session.expires, session.state, account.user_id, account.account_id from session join account on account.account_id = session.account_id where session.session_id = %s and session.expires > %s", session_id, time())

  def _get_account(self, user_id):
    return self.db.get("select account_id, password from account where user_id = %s", user_id)

  def _store_session(self, session_id, session_data):
    account_id = session_data['account_id']
    expires = session_data['expires']
    self.db.execute("delete from session where account_id = %s and expires <= %s", account_id, time())
    self.db.execute("insert into session (account_id, expires, session_id) values (%s, %s, %s)", account_id, expires, session_id)

  def _prepare_session(self, account, session_data):
    session_data['account_id'] = account['account_id']

  def _instantiate_session(self, session_data, session_cache):
    return MySQLdbSession(self.db, session_data, self._session_cache)

  def _update_expiry(self, session_id, session_data):
    self.db.execute("update session set expires = %s where session_id = %s", session_data['expires'], session_id)

  def _update_password(self, user_id, account, hashed_password):
    self.db.execute("update account set password = %s where account_id = %s", hashed_password, account['account_id'])

  def _remove_session(self, session_id):
    self.db.execute("delete from session where session_id = %s", session_id)

  def clear_sessions(self, user_id):
    user_id = user_id.lower()
    self.db.execute("delete from session using session join account on account.account_id = session.account_id where account.user_id = %s", user_id)
