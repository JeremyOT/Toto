import login
from toto.invocation import *

@requires('user_id', 'password')
def invoke(handler, params):
  handler.db_connection.create_account(params['user_id'], params['password'], {k: params[k] for k in params})
  return login.invoke(handler, params)
