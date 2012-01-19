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
