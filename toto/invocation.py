from exceptions import *

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

def authenticated(fn):
  def wrapper(handler, parameters):
    handler.retrieve_session()
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
  @error_redirect must be the outermost decorator if you want it to handle
  errors raised by other decorators.
"""
def error_redirect(redirect_map, default=None):
  def decorator(fn):
    def wrapper(handler, parameters):
      try:
        return fn(handler, parameters)
      raise Exception as e:
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
