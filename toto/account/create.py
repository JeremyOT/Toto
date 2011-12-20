import login

def invoke(handler, params):
  handler.connection.create_account(params['user_id'], params['password'])
  return login.invoke(handler, params)
