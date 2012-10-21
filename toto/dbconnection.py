class DBConnection():
  '''Toto uses subclasses of DBConnection to support session and account storage as well as general
    access to the backing database. Usually, direct access to the underlying database driver will
    be available via the ``DBConnection.db`` property.

    Currently, toto provides the following ``DBConnection`` drivers:

    * ``toto.mongodbconnection.MongoDBConnection``
    * ``toto.mysqldbconnection.MySQLdbConnection``
    * ``toto.postgresconnection.PostgresConnection``
    * ``toto.redisconnection.RedisConnection``
  '''

  def create_account(self, user_id, password, additional_values={}, **values):
    '''Create an account for the given ``user_id`` and ``password``. Optionally set additional account
      values by passing them as keyword arguments (the ``additional_values`` parameter is deprecated).

      Note: if your database uses a predefined schema, make sure to create the appropriate columns
      before passing additional arguments to ``create_account``.
    '''
    raise NotImplementedError()

  def create_session(self, user_id=None, password=None):
    '''Create a new session for the account with the given ``user_id`` and ``password``, or an anonymous
      session if anonymous sessions are enabled. This method returns a subclass of ``TotoSession``
      designed for the current backing database.
    '''
    raise NotImplementedError()

  def retrieve_session(self, session_id, hmac_data=None, data=None):
    '''Retrieve an existing session with the given ``session_id``. Pass the request body and the value
    of the ``x-toto-hmac`` header as ``data`` and ``hmac_data`` respectively to verify an authenticated request.
    If ``hmac_data`` and ``data`` are both ``None``, HMAC verification will be skipped. This method returns a
    subclasses of ``TotoSession`` designed for the current backing database.
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
