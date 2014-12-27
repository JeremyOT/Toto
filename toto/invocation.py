'''``toto.invocation`` contains many decorators that may be applied to the ``invoke(handler, parameters)`` functions in
  method modules in order to modify their behavior.
'''

from exceptions import *
from tornado.options import options
from traceback import format_exc
from tornado.gen import coroutine, Return, engine
from toto.tasks import TaskQueue
import logging
import json

"""
This is a list of all attributes that may be added by a decorator,
it is used to allow decorators to be order agnostic.
"""
invocation_attributes = ['asynchronous', '__doc__', '__module__', '__name__', '__repr__']

def _add_doc(fn, wrapper, doc):
  '''A convenience method for appending to a decorated method's docstring.'''
  wrapper.__name__ = fn.__name__
  wrapper.__module__ = fn.__module__
  wrapper.__doc__ = fn.__doc__ and '%s\n\n%s' % (fn.__doc__, doc) or doc

def _copy_attributes(fn, wrapper, doc=None, attributes=invocation_attributes):
  '''A convenience method for copying certain attributes to a decorated method. Optionally, ``doc``
  can be passed to append to a the method's docstring. To specify which attributes to copy, pass
  an iterable as the ``attributes`` argument.
  '''
  for a in attributes:
    if hasattr(fn, a):
      setattr(wrapper, a, getattr(fn, a))
  if doc:
    _add_doc(fn, wrapper, doc)

def asynchronous(fn):
  '''Invoke functions with the ``@asynchronous`` decorator will not cause the request
  handler to finish when they return. Use this decorator to support long running
  operations like tasks sent to workers or long polling.
  '''
  fn.asynchronous = True
  return fn

def anonymous_session(fn):
  '''Invoke functions marked with the ``@anonymous_session`` decorator will attempt to load
  the current session (either referenced by the x-toto-session-id request headers or cookie).
  If no session is found, an anonymous session will be created.

  Note: If the user was previously authenticated, the authenticated session
  will be loaded.
  '''
  def wrapper(handler, parameters):
    handler.retrieve_session()
    if not handler.session:
      handler.create_session()
    return fn(handler, parameters)
  _copy_attributes(fn, wrapper, '*If not authenticated, this request will use an anonymous session for state persistence*.')
  return wrapper

def authenticated(fn):
  '''Invoke functions marked with the ``@authenticated`` decorator will attempt to
  load the current session (either referenced by the x-toto-session-id request header or cookie).
  If no session is found, or if the current session is anonymous, a "Not authorized"
  error will be returned to the client.
  '''
  def wrapper(handler, parameters):
    handler.retrieve_session()
    if not handler.session or not handler.session.user_id:
      raise TotoException(ERROR_NOT_AUTHORIZED, "Not authorized")
    return fn(handler, parameters)
  _copy_attributes(fn, wrapper, '*Requires authentication*.')
  return wrapper

def optionally_authenticated(fn):
  '''Invoke functions marked with the ``@optionally_authenticated`` decorator will
  attempt to load the current session (either referenced by the x-toto-session-id request header or cookie).
  If no session is found, the request proceeds as usual.
  '''
  def wrapper(handler, parameters):
    handler.retrieve_session()
    return fn(handler, parameters)
  _copy_attributes(fn, wrapper)
  return wrapper

def authenticated_with_parameter(fn):
  '''Invoke functions marked with the ``@authenticated_with_parameter`` decorator will
  behave like functions decorated with ``@authenticated`` but will use the session_id
  parameter to find the current session instead of the x-toto-session-id header or cookie.
  '''
  def wrapper(handler, parameters):
    if 'session_id' in parameters:
      handler.retrieve_session(parameters['session_id'])
      del parameters['session_id']
    if not handler.session:
      raise TotoException(ERROR_NOT_AUTHORIZED, "Not authorized")
    return fn(handler, parameters)
  _copy_attributes(fn, wrapper, '*Authenticated session. Requires the session to be passed as* ``session_id``.')
  return wrapper

def requires(*args):
  '''Invoke functions marked with the ``@requires`` decorator will error if any of the parameters
  passed to the decorator are missing. The following example will error if either "param1" or "param2"
  is not included in the request::

    @requires('param1', 'param2')
    def invoke(handler, parameters):
      pass
  '''
  required_parameters = set(args)
  def decorator(fn):
    def wrapper(handler, parameters):
      missing_parameters = required_parameters.difference(parameters)
      if missing_parameters:
        raise TotoException(ERROR_MISSING_PARAMS, "Missing parameters: " + ', '.join(missing_parameters))
      return fn(handler, parameters)
    _copy_attributes(fn, wrapper, '*Required parameters:* %s.' % ', '.join('``%s``' % i for i in args))
    return wrapper
  return decorator

def raw_response(fn):
  '''Invoke functions marked with the ``@raw_response`` decorator will not be serialized before response
  to the client. This can be used to send text, html or other binary data without the usual JSON (or other)
  processing. The ``handler.response_type`` property will be used to set the response "Content-Type" header.
  By default this will be "application/octet-stream".
  '''
  def wrapper(handler, parameters):
    handler.response_type = 'application/octet-stream'
    handler.respond_raw(fn(handler, parameters), handler.response_type)
    return None
  _copy_attributes(fn, wrapper)
  return wrapper

def jsonp(callback_name='jsonp'):
  '''Invoke functions marked with the ``@jsonp`` decorator will return a wrapper response that will
  call a client-side javascript function. This decorator requires a "jsonp" parameter set to the name of the javascript
  callback function to be passed with the request. If no "jsonp" parameter is passed, the request will respond
  like any other Toto request. The decorator can be applied with an optional ``callback_name`` argument to
  specify a parameter to use instead of "jsonp", e.g.::

    @jsonp('callback')
    def invoke(handler, parameters):
      #do stuff

  Will allow JSONP requests that call the function specified by "callback" in their response. Applying the
  decorator without the ``callback_name`` parameter will use the default "jsonp"::

    @jsonp
    def invoke(handler, parameters):
      #do stuff

  Note: JSONP requests will only be affected by decorators before ``@jsonp`` in the decorator chain.
  '''
  def decorator(fn):
    def wrapper(handler, parameters):
      callback = parameters.get(callback_name, None)
      if callback:
        del parameters[callback_name]
        handler.respond_raw('%s(%s)' % (callback, json.dumps(fn(handler, parameters))), 'text/javascript')
        return None
      else:
        return fn(handler, parameters)
    _copy_attributes(fn, wrapper, '*Supports JSONP requests with the callback parameter* ``%s``.' % callback_name)
    return wrapper

  if isinstance(callback_name, basestring):
    return decorator
  fn = callback_name
  callback_name = 'jsonp'
  return decorator(fn)

def error_redirect(redirect_map, default=None):
  '''Invoke functions marked with the ``@error_redirect`` decorator will redirect according to the ``redirect_map``
  dictionary. ``redirect_map`` should consist of ``status_code``, ``url`` pairs. This decorator will check the ``code``
  then ``status_code`` properties of the raised error for matches in the redirect map before falling back to the usual
  error behavior. The optional ``default`` parameter can be used to specify a url to redirect to if there are no matches
  in ``redirect_map``.

  The following code will redirect to "not_found.html" on 404, and "error.html" otherwise::

    @error_redirect({'404': 'not_found.html'}, 'error.html')
    def invoke(handler, parameters):
      pass
  '''
  def decorator(fn):
    def wrapper(handler, parameters):
      try:
        return fn(handler, parameters)
      except Exception as e:
        if options.debug:
          logging.error(format_exc())
        if hasattr(e, 'code') and str(e.code) in redirect_map:
          handler.redirect(redirect_map[str(e.code)])
        elif hasattr(e, 'status_code') and str(e.status_code) in redirect_map:
          handler.redirect(redirect_map[str(e.status_code)])
        elif default:
          handler.redirect(default)
        else:
          raise
    _copy_attributes(fn, wrapper)
    return wrapper
  return decorator

def default_parameters(defaults):
  '''Invoke functions marked with the ``@default_parameters`` decorator will set missing parameters according to the
  dictionary passed as the ``defaults`` argument.
  '''
  def decorator(fn):
    def wrapper(handler, parameters):
      for p in defaults:
        if p not in parameters:
          parameters[p] = defaults[p]
      return fn(handler, parameters)
    _copy_attributes(fn, wrapper, '*Automatically adds default parameters:* %s.' % ', '.join(('``%s: %s``' % (k, v) for k, v in defaults.iteritems())))
    return wrapper
  return decorator
