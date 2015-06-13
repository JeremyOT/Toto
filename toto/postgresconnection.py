from toto.exceptions import *
from toto.session import *
from time import time, mktime
from datetime import datetime
from psycopg2.pool import ThreadedConnectionPool
from itertools import izip
import toto.secret as secret
import base64
import uuid
from dbconnection import DBConnection

def pg_get(self, query, parameters=None):
  conn = self.getconn()
  cur = conn.cursor()
  cur.execute(query, parameters)
  result = cur.fetchone()
  self.putconn(conn)
  return result and dict(izip((d[0] for d in cur.description), result))
ThreadedConnectionPool.get = pg_get

def pg_execute(self, query, parameters=None):
  conn = self.getconn()
  cur = conn.cursor()
  cur.execute(query, parameters)
  conn.commit()
  self.putconn(conn)
ThreadedConnectionPool.execute = pg_execute

def pg_query(self, query, parameters=None):
  conn = self.getconn()
  cur = conn.cursor()
  cur.execute(query, parameters)
  columns = [d[0] for d in cur.description]
  for r in cur:
    yield dict(izip(columns, r))
  self.putconn(conn)
ThreadedConnectionPool.query = pg_query


class PostgresSession(TotoSession):
  _account = None

  class PostgresAccount(TotoAccount):

    def __init__(self, session):
      super(PostgresSession.PostgresAccount, self).__init__(session)
      self._properties['account_id'] = session.account_id

    def _load_property(self, *args):
      return self._session._db.get('select ' + ', '.join(args) + ' from account where account_id = %s', (self._session.account_id))

    def _save_property(self, *args):
      self._session._db.execute('update account set ' + ', '.join(['%s = %%s' % k for k in args]) + ' where account_id = %s', ([self[k] for k in args] + [self._session.account_id,]))

    def __setitem__(self, key, value):
      if key != 'account_id':
        super(PostgresSession.PostgresAccount, self).__setitem__(key, value)

  def __init__(self, db, session_data, session_cache=None):
    super(PostgresSession, self).__init__(db, session_data, session_cache)
    self.account_id = session_data['account_id']

  def get_account(self):
    if not self._account:
      self._account = PostgresSession.PostgresAccount(self)
    return self._account

  def session_data(self):
    return {'user_id': self.user_id, 'expires': self.expires, 'session_id': self.session_id, 'state': TotoSession.dumps(self.state), 'account_id': self.account_id}

  def refresh(self):
    session_data = self._refresh_cache() or self._db.get("select session.session_id, session.expires, session.state, account.user_id, account.account_id from session join account on account.account_id = session.account_id where session.session_id = %s", (session_id,))
    self.__init__(session_data, self._session_cache)

  def save(self):
    if not self._save_cache():
      self._db.execute("update session set state = %s where session_id = %s", (TotoSession.dumps(self.state), self.session_id))

class PostgresConnection(DBConnection):

  def create_tables(self):
    if not self.db.get("select table_name from information_schema.tables where table_schema = 'public' and table_name = 'account'"):
      self.db.execute('''create table if not exists account (
        account_id bigserial primary key,
        password char(48) default null,
        user_id varchar(45) not null,
        unique (user_id)
      );''')
    if not self.db.get("select table_name from information_schema.tables where table_schema = 'public' and table_name = 'session'"):
      self.db.execute('''create table if not exists session (
        session_id char(22) not null primary key,
        account_id bigint not null references account (account_id),
        expires double precision not null,
        state bytea
      );''')
      self.db.execute('create index session_expires on session using btree (expires);')

  def __init__(self, host, port, database, username, password, min_connections=1, max_connections=10):
    super(PostgresConnection, self).__init__(*args, **kwargs)
    self.db = ThreadedConnectionPool(min_connections, max_connections, database=database, user=username, password=password, host=host, port=port)
    self.create_tables()

  def _store_session(self, session_id, session_data):
    account_id = session_data['account_id']
    expires = session_data['expires']
    self.db.execute("delete from session where account_id = %s and expires <= %s", (account_id, time()))
    self.db.execute("insert into session (account_id, expires, session_id) values (%s, %s, %s)", (account_id, expires, session_id))

  def _update_expiry(self, session_id, session_data):
    self.db.execute("update session set expires = %s where session_id = %s", (session_data['expires'], session_id))

  def _update_password(self, user_id, account, hashed_password):
    self.db.execute("update account set password = %s where account_id = %s", (hashed_password, account['account_id']))

  def _instantiate_session(self, session_data, session_cache):
    return PostgresSession(self.db, session_data, self._session_cache)

  def _get_account(self, user_id):
    return self.db.get("select account_id, password from account where user_id = %s", (user_id,))

  def _store_account(self, user_id, values):
    self.db.execute("insert into account (" + ', '.join([k for k in values]) + ") values (" + ','.join(['%s' for k in values]) + ")", [values[k] for k in values])

  def _load_uncached_data(self, session_id):
    return self.db.get("select session.session_id, session.expires, session.state, account.user_id, account.account_id from session join account on account.account_id = session.account_id where session.session_id = %s and session.expires > %s", (session_id, time()))

  def _remove_session(self, session_id):
    self.db.execute("delete from session where session_id = %s", (session_id,))

  def clear_sessions(self, user_id):
    user_id = user_id.lower()
    self.db.execute("delete from session using session join account on account.account_id = session.account_id where account.user_id = %s", (user_id,))
