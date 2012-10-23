import login
from toto.invocation import *

@requires('user_id', 'password')
def invoke(handler, params):
  '''Create an account with the given ``user_id`` and ``password`` if no account
  matching the ``user_id`` exists. Any other parameters will be added as
  additional properties of the account. If using a database with a predefined
  schema, make sure they match existing columns, otherwise an error will be
  returned.

  Requires: ``user_id``, ``password``
  '''
  handler.db_connection.create_account(params['user_id'], params['password'], {k: params[k] for k in params})
  return login.invoke(handler, params)
