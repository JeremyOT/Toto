from toto.invocation import *

@authenticated
def invoke(handler, parameters):
  return {'parameters': parameters, 'user_id': handler.session.user_id}
