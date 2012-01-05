from exceptions import *

def asynchronous(fn):
  fn.asynchronous = True
  return fn

def authenticated(fn):
  def wrapper(handler, parameters):
    if not handler.session:
      raise TotoException(ERROR_NOT_AUTHORIZED, "Not authorized")
    return fn(handler, parameters)
  return wrapper

def requires(*args):
  required_parameters = set(args)
  def decorator(fn):
    def wrapper(handler, parameters):
      missing_parameters = required_parameters.difference(parameters)
      if missing_parameters:
        raise TotoException(ERROR_MISSING_PARAMS, "Missing parameters: " + ', '.join(missing_parameters))
      return fn(handler, parameters)
    return wrapper
  return decorator
