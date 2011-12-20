ERROR_SERVER = 1000
ERROR_MISSING_METHOD = 1002
ERROR_MISSING_PARAMS = 1003
ERROR_NOT_AUTHORIZED = 1004
ERROR_USER_NOT_FOUND = 1005
ERROR_USER_ID_EXISTS = 1006
ERROR_INVALID_SESSION_ID = 1007
ERROR_INVALID_HMAC = 1008

class TotoError(Exception):
  def __init__(self, code, value):
    self.value = value
    self.code = code
  def __str__(self):
    return json.dumps(self.__dict__)
