from toto.invocation import *

@authenticated
def invoke(handler, parameters):
  '''Invalidates the current authenticated session. If the request is
  not authenticated, a "Not authorized" error will be returned.
  '''
  handler.db_connection.remove_session(handler.session.session_id)
  return {'authenticated': False}
