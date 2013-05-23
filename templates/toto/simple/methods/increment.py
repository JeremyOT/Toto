from toto.invocation import *

@authenticated
def invoke(handler, params):
  handler.session['counter'] = (handler.session['counter'] or 0) + 1
  handler.session.save()
  return {'count': handler.session['counter']}
