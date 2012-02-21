from toto.invocation import *

@requires('user_id', 'password')
def invoke(handler, params):
  handler.create_session(params['user_id'], params['password'])
  return {'session_id': handler.session.session_id, 'expires': handler.session.expires, 'user_id': handler.session.user_id}
