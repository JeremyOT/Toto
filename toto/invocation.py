from exceptions import *
from tornado.options import options
from traceback import format_exc
import logging

"""
This is a list of all attributes that may be added by a decorator,
it is used to allow decorators to be order agnostic.
"""
invocation_attributes = ["asynchronous",]

def __copy_attributes(fn, wrapper):
  for a in invocation_attributes:
    if hasattr(fn, a):
      setattr(wrapper, a, getattr(fn, a))

def asynchronous(fn):
  fn.asynchronous = True
  return fn

def anonymous_session(fn):
  def wrapper(handler, parameters):
    handler.retrieve_session()
    if not handler.session:
      handler.create_session()
    return fn(handler, parameters)
  __copy_attributes(fn, wrapper)
  return wrapper

def authenticated(fn):
  def wrapper(handler, parameters):
    handler.retrieve_session()
    if not handler.session:
      raise TotoException(ERROR_NOT_AUTHORIZED, "Not authorized")
    return fn(handler, parameters)
  __copy_attributes(fn, wrapper)
  return wrapper

def authenticated_with_parameter(fn):
  def wrapper(handler, parameters):
    if 'session_id' in parameters:
      handler.retrieve_session(parameters['session_id'])
      del parameters['session_id']
    if not handler.session:
      raise TotoException(ERROR_NOT_AUTHORIZED, "Not authorized")
    return fn(handler, parameters)
  __copy_attributes(fn, wrapper)
  return wrapper

def requires(*args):
  required_parameters = set(args)
  def decorator(fn):
    def wrapper(handler, parameters):
      missing_parameters = required_parameters.difference(parameters)
      if missing_parameters:
        raise TotoException(ERROR_MISSING_PARAMS, "Missing parameters: " + ', '.join(missing_parameters))
      return fn(handler, parameters)
    __copy_attributes(fn, wrapper)
    return wrapper
  return decorator

"""
  Return the desired response body as a string. Optionally, set handler.response_type
  to the mime type of your response.
"""
def raw_response(fn):
  def wrapper(handler, parameters):
    handler.response_type = 'application/octet-stream'
    handler.respond_raw(fn(handler, parameters), handler.response_type, False)
    return None
  __copy_attributes(fn, wrapper)
  return wrapper

"""
  Requires the parameter 'jsonp=<callback_function>' to be passed in the query string (meaning method_select
  must be set to either 'both' or 'url'). This parameter will be stripped before the
  parameters are passed to the decorated function.
"""
def jsonp(fn):
  def wrapper(handler, parameters):
    callback = parameters['jsonp']
    del parameters['jsonp']
    handler.respond_raw('%s(%s)' % (callback, fn(handler, parameters)), 'text/javascript')
    return None
  __copy_attributes(fn, wrapper)
  return wrapper

"""
  @error_redirect must be the outermost decorator if you want it to handle
  errors raised by other decorators.
"""
def error_redirect(redirect_map, default=None):
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
    __copy_attributes(fn, wrapper)
    return wrapper
  return decorator

def default_parameters(defaults):
  def decorator(fn):
    def wrapper(handler, parameters):
      for p in defaults:
        if p not in parameters:
          parameters[p] = defaults[p]
      return fn(handler, parameters)
    __copy_attributes(fn, wrapper)
    return wrapper
  return decorator
