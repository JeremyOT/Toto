import toto.methods.account.login
from toto.invocation import *

@authenticated
def invoke(handler, params):
  result = {'updated_fields': []}
  if 'new_password' in params:
    handler.db_connection.change_password(params['user_id'], params['password'], params['new_password'])
    result['updated_fields'].append('password')
    result.update(login.invoke(handler, {'user_id': params['user_id'], 'password': params['new_password']}))
    del params['new_password']
  del params['password']
  account = handler.session.get_account()
  for k in params:
    account[k] = params[k]
    result['updated_fields'].append(k)
    account.save()
  return result
  
