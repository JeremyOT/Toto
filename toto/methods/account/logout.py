from toto.invocation import *

@authenticated
def invoke(handler, parameters):
  handler.connection.remove_session(handler.session.session_id)
  return {'authenticated': False}
