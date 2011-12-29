def asynchronous(fn):
  setattr(fn, "asynchronous", True)
  return fn

def authenticated(fn):
  setattr(fn, "authenticated", True)
  return fn
