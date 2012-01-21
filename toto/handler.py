from tornado.web import *
import json
import hashlib
import hmac
from invocation import *
from exceptions import *
from tornado.options import define, options
import base64

define("bson_enabled", default=False, help="Allows requests to use BSON with content-type application/bson")
define("allow_origin", default="*", help="This is the value for the Access-Control-Allow-Origin header (default *)")

class TotoHandler(RequestHandler):

  SUPPORTED_METHODS = ["POST", "OPTIONS"]
  ACCESS_CONTROL_ALLOW_ORIGIN = options.allow_origin

  def initialize(self, method_root, connection):
    self.__method_root = method_root
    self.connection = connection
    self.bson = options.bson_enabled and __import__('bson').BSON

  """
    Lookup method by name: a.b.c loads api/a/b/c.py
  """
  def __get_method(self, method_name):
    method_path = method_name.split('.')
    method = self.__method_root
    while method_path:
      method = getattr(method, method_path.pop(0))
    return method.invoke

  def options(self):
    allowed_headers = set(['x-toto-hmac','x-toto-session-id','origin','content-type'])
    if 'access-control-request-headers' in self.request.headers:
      allowed_headers = allowed_headers.union(self.request.headers['access-control-request-headers'].lower().replace(' ','').split(','))
    self.add_header('access-control-allow-headers', ','.join(allowed_headers))
    if 'access-control-request-method' in self.request.headers and self.request.headers['access-control-request-method'] not in self.SUPPORTED_METHODS:
      raise HTTPError(405, 'Method not supported')
    self.add_header('access-control-allow-origin', self.ACCESS_CONTROL_ALLOW_ORIGIN)
    self.add_header('access-control-allow-methods', ','.join(self.SUPPORTED_METHODS))
    self.add_header('access-control-expose-headers', 'x-toto-hmac')

  @tornado.web.asynchronous
  def post(self):
    self.session = None
    self.__method = None
    headers = self.request.headers
    response = {}
    use_bson = self.bson and 'content-type' in headers and headers['content-type'] == 'application/bson'
    self.add_header('access-control-allow-origin', self.ACCESS_CONTROL_ALLOW_ORIGIN)
    self.add_header('access-control-expose-headers', 'x-toto-hmac')
    try:
      if use_bson:
        body = self.bson(self.request.body).decode()
      else:
        body = json.loads(self.request.body)
      if 'method' not in body:
        raise TotoException(ERROR_MISSING_METHOD, "Missing method.")
      self.__method = self.__get_method(body['method'])
      if 'x-toto-session-id' in headers:
        self.session = self.connection.retrieve_session(headers['x-toto-session-id'], 'x-toto-hmac' in headers and headers['x-toto-hmac'] or None, self.request.body)
      if not 'parameters' in body:
        raise TotoException(ERROR_MISSING_PARAMS, "Missing parameters.")
      response['result'] = self.__method(self, body['parameters'])
    except TotoException as e:
      response['error'] = e.__dict__
    except Exception as e:
      response['error'] = TotoException(ERROR_SERVER, str(e)).__dict__
    if response['result'] is not None or 'error' in response:
      if use_bson:
        self.add_header('content-type', 'application/bson')
        response_body = str(self.bson.encode(response))
      else:
        self.add_header('content-type', 'application/json')
        response_body = json.dumps(response)
      if self.session:
        self.add_header('x-toto-hmac', base64.b64encode(hmac.new(str(self.session.user_id), response_body, hashlib.sha1).digest()))
      self.write(response_body)
    if not hasattr(self.__method, 'asynchronous'):
      print "FINISH"
      self.finish()

  def on_connection_close(self):
    if hasattr(self.__method, 'on_connection_close'):
      self.__method.on_connection_close();

