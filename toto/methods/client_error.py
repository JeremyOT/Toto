import logging
from toto.invocation import *

@requires('client_error', 'client_type')
def invoke(handler, parameters):
  '''A convenince method for writing browser errors
  to Toto's server log. It works with the ``registerErrorHandler()`` method in ``toto.js``.

  The "client_error" parameter should be set to the string to be written to Toto's log.
  Currently, the "client_type" parameter must be set to "browser_js" for an event
  to be written. Otherwise, this method has no effect.

  Requires: ``client_error``, ``client_type``
  '''
  if parameters['client_type'] != 'browser_js':
    return {'logged': False}
  logging.error(str(parameters['client_error']))
  return {'logged': True}
