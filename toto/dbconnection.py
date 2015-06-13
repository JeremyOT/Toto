from toto.exceptions import *
from toto.session import *
import toto.secret as secret
from time import time
import random
import string
from toto.tasks import InstancePool

class DBConnection(object):
  '''Toto uses subclasses of DBConnection to support session and account storage as well as general
    access to the backing database. Usually, direct access to the underlying database driver will
    be available via the ``DBConnection.db`` property.

    Currently, toto provides the following ``DBConnection`` drivers:

    * ``toto.mongodbconnection.MongoDBConnection``
    * ``toto.mysqldbconnection.MySQLdbConnection``
    * ``toto.postgresconnection.PostgresConnection``
    * ``toto.redisconnection.RedisConnection``
    * ``toto.jsondbconnection.JSONConnection`` (For debugging only)
  '''

  _session_cache = None

  def __init__(self, session_ttl=24*60*60*365, anon_session_ttl=24*60*60, session_renew=0, anon_session_renew=0, *args, **kwargs):
    self.session_ttl = session_ttl
    self.anon_session_ttl = anon_session_ttl or self.session_ttl
    self.session_renew = session_renew or self.session_ttl
    self.anon_session_renew = anon_session_renew or self.anon_session_ttl

  def create_account(self, user_id, password, additional_values={}, **values):
    '''Create an account for the given ``user_id`` and ``password``. Optionally set additional account
      values by passing them as keyword arguments (the ``additional_values`` parameter is deprecated).

      Note: if your database uses a predefined schema, make sure to create the appropriate columns
      before passing additional arguments to ``create_account``.
    '''
    if not user_id:
      raise TotoException(ERROR_INVALID_USER_ID, "Invalid user ID.")
    user_id = user_id.lower()
    account = self._get_account(user_id)
    if account:
      raise TotoException(ERROR_USER_ID_EXISTS, "User ID already in use.")
    values.update(additional_values)
    values['user_id'] = user_id
    values['password'] = secret.password_hash(password)
    self._store_account(user_id, values)

  def create_session(self, user_id=None, password=None, verify_password=True, key=None):
    '''Create a new session for the account with the given ``user_id`` and ``password``, or an anonymous
      session if anonymous sessions are enabled. This method returns a subclass of ``TotoSession``
      designed for the current backing database. Pass ``verify_password=False`` to create a session
      without checking the password. This feature can be used to implement alternative authentication
      methods like Facebook, Twitter or Google+.
    '''
    if not user_id:
      user_id = ''
    user_id = user_id.lower()
    account = user_id and self._get_account(user_id)
    if user_id and (not account or (verify_password and not secret.verify_password(password, account['password']))):
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID or password")
    session_id = TotoSession.generate_id()
    expires = time() + (user_id and self.session_ttl or self.anon_session_ttl)
    session_data = {'user_id': user_id, 'expires': expires, 'session_id': session_id}
    if key:
      session_data['key'] = key
    self._prepare_session(account, session_data)
    if not self._cache_session_data(session_data):
      self._store_session(session_id, session_data)
    session = self._instantiate_session(session_data, self._session_cache)
    return session

  def retrieve_session(self, session_id):
    '''Retrieve an existing session with the given ``session_id``. This method returns a
    subclass of ``TotoSession`` designed for the current backing database.

    The use of HTTPS is strongly recommended for any communication involving sensitive information.
    '''
    session_data = self._load_session_data(session_id)
    if not session_data:
      return None
    user_id = session_data['user_id']
    expires = time() + (user_id and self.session_renew or self.anon_session_renew)
    if session_data['expires'] < expires:
      session_data['expires'] = expires
      if not self._cache_session_data(session_data):
        self._update_expiry(session_id, session_data)
    session = self._instantiate_session(session_data, self._session_cache)
    return session

  def change_password(self, user_id, password, new_password):
    '''Updates the password for the account with the given ``user_id`` and ``password`` to match
    ``new_password`` for all future requests.
    '''
    user_id = user_id.lower()
    account = self._get_account(user_id)
    if not account or not secret.verify_password(password, account['password']):
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID or password")
    self._update_password(user_id, account, secret.password_hash(new_password))

  def generate_password(self, user_id):
    '''Generates a new password for the account with the given ``user_id`` and makes it active
    for all future requests. The new password will be returned. This method is designed to
    support "forgot password" functionality.
    '''
    user_id = user_id.lower()
    account = self._get_account(user_id)
    if not account:
      raise TotoException(ERROR_USER_NOT_FOUND, "Invalid user ID")
    pass_chars = string.ascii_letters + string.digits
    new_password = ''.join([random.choice(pass_chars) for x in xrange(10)])
    self._update_password(user_id, account, secret.password_hash(new_password))
    return new_password

  def remove_session(self, session_id):
    '''Invalidate the session with the given ``session_id``.
    '''
    if self._session_cache:
      self._session_cache.remove_session(session_id)
    else:
      self._remove_session(session_id)

  def _remove_session(self, session_id):
    '''Called by ``DBConnection.remove_session`` to invalidate the specified session when no session cache is in use.
    '''
    raise NotImplementedError()

  def clear_sessions(self, user_id):
    '''If implemented, invalidates all sessions tied to the account with the given ``user_id``.
    '''
    pass

  def set_session_cache(self, session_cache):
    '''Optionally set an instance of ``TotoSessionCache`` that will be used to store sessions separately from
    this database.
    '''
    self._session_cache = session_cache

  def _load_session_data(self, session_id):
    '''Called by ``DBConnection.retrieve_session``. Will attempt to load data from an associated ``TotoSessionCache``.
    If no ``TotoSessionCache`` is associated with the current instance, the result of ``self._load_uncached_data(session_id)``
    is returned.
    '''
    if self._session_cache:
      return self._session_cache.load_session(session_id)
    return self._load_uncached_data(session_id)

  def _load_uncached_data(self, session_id):
    '''Load a session data ``dict`` from the local database. Called by default and if no ``TotoSessionCache`` has been
    associated with the current instance of ``DBConnection``.
    '''
    raise NotImplementedError()

  def _cache_session_data(self, session_data):
    '''Called by ``DBConnection.create_session`` and by ``DBConnection.retrieve_session`` if there is a change in ``TotoSession.expires``.
    Returns ``True`` if the session has been written to an associated ``TotoSessionCache``, ``False`` otherwise.
    '''
    if self._session_cache:
      updated_session_id = self._session_cache.store_session(session_data)
      if updated_session_id:
        session_data['session_id'] = updated_session_id
      return True
    return False

  def _store_session(self, session_id, session_data):
    '''Called by ``DBConnection.create_session``, and by ``DBConnection.retrieve_session`` if there is a change in ``TotoSession.expires``.
    Will not be called if a session cache has been attached to the ``DBConnection``.
    '''
    raise NotImplementedError()

  def _update_expiry(self, session_id, session_data):
    '''Called by ``DBConnection.retrieve_session`` if there is a change in ``TotoSession.expires`` to allow optional efficient updates.
    If not implemented, ``self._store_session`` will be called.
    '''
    return self._store_session(session_id, session_data)

  def _update_password(self, user_id, hashed_password):
    '''Called by ``DBConnection.change_password`` and ``DBConnection.generate_password``.
    '''
    raise NotImplementedError()

  def _instantiate_session(self, session_data, session_cache):
    '''Called by ``DBConnection.create_session`` and by ``DBConnection.retrieve_session`` to actually instantiate a ``TotoSession``
    instance. Must return a new ``TotoSession``.
    '''
    raise NotImplementedError()

  def _get_account(self, user_id):
    '''Called by ``DBConnection.create_session`` if ``verify_password=True`` and must return a dictionry containing
    at least the pair ``'password':<hashed_password``.
    '''
    raise NotImplementedError()

  def _prepare_session(self, account, session_data):
    '''Called by ``DBConnection.create_session`` before the session is written to the database to allow for the
    addition of any extra data that may be needed by the ``subclass.TotoSession`` implementation.
    '''
    pass

  def _store_account(self, user_id, values):
    '''Must be implemented in subclasses to persist new accounts to the database. Values is a dictionary
    that will contain, at a minimum, ``user_id`` and ``password``. ``password`` will be the hashed password
    passed to ``self.create_account()``.
    '''
    raise NotImplementedError()

from tornado.options import define, options

define("database", metavar='mysql|mongodb|redis|postgres|json|none', default="none", help="the database driver to use")
define("db_host", default='localhost', help="The host to use for database connections.")
define("db_port", default=0, help="The port to use for database connections. Leave this at zero to use the default for the selected database type")
define("mysql_database", type=str, help="Main MySQL schema name")
define("mysql_user", type=str, help="Main MySQL user")
define("mysql_password", type=str, help="Main MySQL user password")
define("mysql_uuid_account_id", default=False, help="Use binary(16) UUIDs for account_id in MySQL databases instead of int(8) unsigned auto_increment. UUID(bytes=handler.session.account_id) can be used to get a UUID representing the account_id.")
define("postgres_database", type=str, help="Main Postgres database name")
define("postgres_user", type=str, help="Main Postgres user")
define("postgres_password", type=str, help="Main Postgres user password")
define("postgres_min_connections", type=int, default=1, help="The minimum number of connections to keep in the Postgres connection pool")
define("postgres_max_connections", type=int, default=100, help="The maximum number of connections to keep in the Postgres connection pool")
define("mongodb_database", default="toto_server", help="MongoDB database")
define("redis_database", default=0, help="Redis DB")
define("session_ttl", default=24*60*60*365, help="The number of seconds after creation a session should expire")
define("anon_session_ttl", default=24*60*60, help="The number of seconds after creation an anonymous session should expire")
define("session_renew", default=0, help="The number of seconds before a session expires that it should be renewed, or zero to renew on every request")
define("anon_session_renew", default=0, help="The number of seconds before an anonymous session expires that it should be renewed, or zero to renew on every request")

def configured_connection():
    '''Returns a new database connection based on the configuration options
    '''
    if options.database == "mongodb":
      from mongodbconnection import MongoDBConnection
      return MongoDBConnection(options.db_host, options.db_port or 27017, options.mongodb_database, session_ttl=options.session_ttl, anon_session_ttl=options.anon_session_ttl, session_renew=options.session_renew, anon_session_renew=options.anon_session_renew)
    elif options.database == "redis":
      from redisconnection import RedisConnection
      return RedisConnection(options.db_host, options.db_port or 6379, options.redis_database, session_ttl=options.session_ttl, anon_session_ttl=options.anon_session_ttl, session_renew=options.session_renew, anon_session_renew=options.anon_session_renew)
    elif options.database == "mysql":
      from mysqldbconnection import MySQLdbConnection
      return MySQLdbConnection('%s:%s' % (options.db_host, options.db_port or 3306), options.mysql_database, options.mysql_user, options.mysql_password, session_ttl=options.session_ttl, anon_session_ttl=options.anon_session_ttl, session_renew=options.session_renew, anon_session_renew=options.anon_session_renew, uuid_account_id=options.mysql_uuid_account_id)
    elif options.database == 'postgres':
      from postgresconnection import PostgresConnection
      return PostgresConnection(options.db_host, options.db_port or 5432, options.postgres_database, options.postgres_user, options.postgres_password, session_ttl=options.session_ttl, anon_session_ttl=options.anon_session_ttl, session_renew=options.session_renew, anon_session_renew=options.anon_session_renew, min_connections=options.postgres_min_connections, max_connections=options.postgres_max_connections)
    elif options.database == 'json':
      from jsondbconnection import JSONConnection
      # return JSONConnection(options.db_host, options.db_port, session_ttl=options.session_ttl, anon_session_ttl=options.anon_session_ttl, session_renew=options.session_renew, anon_session_renew=options.anon_session_renew)
      return InstancePool(JSONConnection(options.db_host, options.db_port, session_ttl=options.session_ttl, anon_session_ttl=options.anon_session_ttl, session_renew=options.session_renew, anon_session_renew=options.anon_session_renew))
    else:
      from fakeconnection import FakeConnection
      return FakeConnection()
