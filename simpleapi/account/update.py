import login

def invoke(handler, params):
  result = {'updated_fields': []}
  if 'new_password' in params:
    handler.connection.change_password(params['user_id'], params['password'], params['new_password'])
    result['updated_fields'].append('password')
    result.update(login.invoke(handler, {'user_id': params['user_id'], 'password': params['new_password']}))
  return result
  
