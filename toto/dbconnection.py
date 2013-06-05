class DBConnection(object):
  '''Toto uses subclasses of DBConnection to support session and account storage as well as general
    access to the backing database. Usually, direct access to the underlying database driver will
    be available via the ``DBConnection.db`` property.

    Currently, toto provides the following ``DBConnection`` drivers:

    * ``toto.mongodbconnection.MongoDBConnection``
    * ``toto.mysqldbconnection.MySQLdbConnection``
    * ``toto.postgresconnection.PostgresConnection``
    * ``toto.redisconnection.RedisConnection``
  '''

  _session_cache = None

  def create_account(self, user_id, password, additional_values={}, **values):
    '''Create an account for the given ``user_id`` and ``password``. Optionally set additional account
      values by passing them as keyword arguments (the ``additional_values`` parameter is deprecated).

      Note: if your database uses a predefined schema, make sure to create the appropriate columns
      before passing additional arguments to ``create_account``.
    '''
    raise NotImplementedError()

  def create_session(self, user_id=None, password=None, verify_password=True):
    '''Create a new session for the account with the given ``user_id`` and ``password``, or an anonymous
      session if anonymous sessions are enabled. This method returns a subclass of ``TotoSession``
      designed for the current backing database. Pass ``verify_password=False`` to create a session
      without checking the password. This feature can be used to implement alternative authentication
      methods like Facebook, Twitter or Google+.
    '''
    raise NotImplementedError()

  def retrieve_session(self, session_id, hmac_data=None, data=None):
    '''Retrieve an existing session with the given ``session_id``. Pass the request body and the value
    of the ``x-toto-hmac`` header as ``data`` and ``hmac_data`` respectively to verify an authenticated request.
    If ``hmac_data`` and ``data`` are both ``None``, HMAC verification will be skipped. This method returns a
    subclasses of ``TotoSession`` designed for the current backing database.

    Toto uses HMAC verification to ensure that requests and responses are not corrupted in transmission.
    The session's ``user_id`` is used as the key which makes it easy for an attacker to forge a request
    so long as they have an active session ID and the associated user ID - both of which are contained
    in the response body of each authenticated request. A future update may contain an option to use
    a secret key for HMAC verification instead.

    The use of HTTPS is strongly recommended for any communication involving sensitive information.
    '''
    raise NotImplementedError()

  def remove_session(self, session_id):
    '''Invalidate the session with the given ``session_id``.
    '''
    raise NotImplementedError()

  def clear_sessions(self, user_id):
    '''If implemented, invalidates all sessions tied to the account with the given ``user_id``.
    '''
    pass

  def change_password(self, user_id, password, new_password):
    '''Updates the password for the account with the given ``user_id`` and ``password`` to match
    ``new_password`` for all future requests.
    '''
    raise NotImplementedError()

  def generate_password(self, user_id):
    '''Generates a new password for the account with the given ``user_id`` and makes it active
    for all future requests. The new password will be returned. This method is designed to
    support "forgot password" functionality.
    '''
    raise NotImplementedError()

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
      self._session_cache.store_session(session_data)
      return True
    return False

from tornado.options import define, options

define("database", metavar='mysql|mongodb|redis|postgres|none', default="none", help="the database driver to use")
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
    if options.database == "mongodb":
      from mongodbconnection import MongoDBConnection
      return MongoDBConnection(options.db_host, options.db_port or 27017, options.mongodb_database, options.session_ttl, options.anon_session_ttl, options.session_renew, options.anon_session_renew)
    elif options.database == "redis":
      from redisconnection import RedisConnection
      return RedisConnection(options.db_host, options.db_port or 6379, options.redis_database, options.session_ttl, options.anon_session_ttl, options.session_renew, options.anon_session_renew)
    elif options.database == "mysql":
      from mysqldbconnection import MySQLdbConnection
      return MySQLdbConnection('%s:%s' % (options.db_host, options.db_port or 3306), options.mysql_database, options.mysql_user, options.mysql_password, options.session_ttl, options.anon_session_ttl, options.session_renew, options.anon_session_renew, options.mysql_uuid_account_id)
    elif options.database == 'postgres':
      from postgresconnection import PostgresConnection
      return PostgresConnection(options.db_host, options.db_port or 5432, options.postgres_database, options.postgres_user, options.postgres_password,  options.session_ttl, options.anon_session_ttl, options.session_renew, options.anon_session_renew, options.postgres_min_connections, options.postgres_max_connections)
    else:
      from fakeconnection import FakeConnection
      return FakeConnection() 
