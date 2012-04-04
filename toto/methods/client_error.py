import logging
from toto.invocation import *

@requires('client_error', 'client_type')
def invoke(handler, parameters):
  if parameters['client_type'] != 'browser_js':
    return {'logged': False}
  logging.error(str(parameters['client_error']))
  return {'logged': True}
