'''Toto uses the following error codes internally:

  * ``ERROR_SERVER = 1000``
  * ``ERROR_MISSING_METHOD = 1002``
  * ``ERROR_MISSING_PARAMS = 1003``
  * ``ERROR_NOT_AUTHORIZED = 1004``
  * ``ERROR_USER_NOT_FOUND = 1005``
  * ``ERROR_USER_ID_EXISTS = 1006``
  * ``ERROR_INVALID_SESSION_ID = 1007``
  * ``ERROR_INVALID_HMAC = 1008``
  * ``ERROR_INVALID_RESPONSE_HMAC = 1009``
  * ``ERROR_INVALID_USER_ID 1010``
'''

ERROR_SERVER = 1000
ERROR_INVALID_METHOD = 1001
ERROR_MISSING_METHOD = 1002
ERROR_MISSING_PARAMS = 1003
ERROR_NOT_AUTHORIZED = 1004
ERROR_USER_NOT_FOUND = 1005
ERROR_USER_ID_EXISTS = 1006
ERROR_INVALID_SESSION_ID = 1007
ERROR_INVALID_HMAC = 1008
ERROR_INVALID_RESPONSE_HMAC = 1009
ERROR_INVALID_USER_ID = 1010

class TotoException(Exception):
  '''This class is used to return errors from Toto methods. ``TotoException.value``
  is used to describe the exception and ``TotoException.code`` should be set to a
  status code that can be used to programmatically reference the exception. Toto's
  error redirecting capabilities use ``code`` to look up the redirect URL.
  '''
  def __init__(self, code, value):
    self.value = value
    self.code = code
  def __str__(self):
    return str(self.__dict__)
  def __repr__(self):
    return repr(self.__dict__)
