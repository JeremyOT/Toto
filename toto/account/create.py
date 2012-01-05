import login
from toto.invocation import *

@requires('user_id', 'password')
def invoke(handler, params):
  handler.connection.create_account(params['user_id'], params['password'])
  return login.invoke(handler, params)
