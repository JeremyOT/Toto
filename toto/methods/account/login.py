from toto.invocation import *

@requires('user_id', 'password')
def invoke(handler, params):
  '''Creates a new session for the account matching ``user_id`` and ``password``. If no
  matching account is found, a "User not found" error will be returned.

  Requires: ``user_id``, ``password``
  '''
  handler.create_session(params['user_id'], params['password'])
  return {'session_id': handler.session.session_id, 'expires': handler.session.expires, 'user_id': handler.session.user_id}
