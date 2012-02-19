from tornado.web import *
import json
import hashlib
import hmac
from invocation import *
from exceptions import *
from tornado.options import define, options
import base64
from events import EventManager
import logging

define("bson_enabled", default=False, help="Allows requests to use BSON with content-type application/bson")
define("allow_origin", default="*", help="This is the value for the Access-Control-Allow-Origin header (default *)")
define("debug", default=False, help="Set this to true to prevent Toto from nicely formatting generic errors. With debug=True, errors will print to the command line")
define("method_select", default="both", metavar="both|url|parameter", help="Selects whether methods can be specified via URL, parameter in the message body or both (default both)")
define("use_cookies", default=False, help="Select whether to use cookies for session storage, replacing the x-toto-session-id header. You must set cookie_secret if using this option and secure_cookies is not set to False (default False)")
define("secure_cookies", default=True, help="If using cookies, select whether or not they should be secure. Secure cookies require cookie_secret to be set (default True)")
define("cookie_domain", default=None, type=str, help="The value to use for the session cookie's domain attribute - e.g. '.example.com' (default None)")

class TotoHandler(RequestHandler):

  SUPPORTED_METHODS = ["POST", "OPTIONS", "GET"]
  ACCESS_CONTROL_ALLOW_ORIGIN = options.allow_origin

  def initialize(self, method_root, connection):
    self.__method_root = method_root
    self.connection = connection
    self.bson = options.bson_enabled and __import__('bson').BSON
    self.response_type = 'application/json'
    self.body = None

  """
    Runtime method configuration
  """
  @classmethod
  def configure(cls):
    #Method configuration
    if options.method_select == 'url':
      def get_method_path(self, path, body):
        if path:
          self.method_path = path.split('/')
        else:
          raise TotoException(ERROR_MISSING_METHOD, "Missing method.")
      cls.__get_method_path = get_method_path
    elif options.method_select == 'parameter':
      def get_method_path(self, path, body):
        if 'method' in body:
          self.method_path = body['method'].split('.')
        else:
          raise TotoException(ERROR_MISSING_METHOD, "Missing method.")
      cls.__get_method_path = get_method_path
    
    if options.use_cookies:
      import math
      set_cookie = options.secure_cookies and cls.set_secure_cookie or cls.set_cookie
      get_cookie = options.secure_cookies and cls.get_secure_cookie or cls.get_cookie
      def create_session(self, user_id, password, ttl=0):
        self.session = self.connection.create_session(user_id, password, ttl)
        set_cookie(self, name='toto-session-id', value=self.session.session_id, expires_days=math.ceil(self.session.expires / (24.0 * 60.0 * 60.0)), domain=options.cookie_domain)
        return self.session
      cls.create_session = create_session
      def retrieve_session(self):
        headers = self.request.headers
        session_id = 'x-toto-session-id' in headers and headers['x-toto-session-id'] or get_cookie(self, 'toto-session-id')
        if session_id:
          self.session = self.connection.retrieve_session(session_id, 'x-toto-hmac' in headers and headers['x-toto-hmac'] or None, self.request.body)
        return self.session
      cls.retrieve_session = retrieve_session
    if options.debug:
      import traceback
      def invoke_method(self, path):
        result = None
        error = None
        try:
          self.__get_method_path(path, self.body)
          self.__get_method()
          result = self.__method(self, self.parameters)
        except TotoException as e:
          logging.error(traceback.format_exc())
          error = e.__dict__
        except Exception as e:
          logging.error(traceback.format_exc())
          error = TotoException(ERROR_SERVER, str(e)).__dict__
        return result, error
      cls.invoke_method = invoke_method
      
  """
    The default method_select "both" (or any unsupported value) will
    call this method. The class method configure() will update this
    to a more efficient method according to the tornado.options
  """
  def __get_method_path(self, path, body):
    if path:
      self.method_path = path.split('/')
    elif 'method' in body:
      self.method_path = body['method'].split('.')
    else:
      raise TotoException(ERROR_MISSING_METHOD, "Missing method.")

  def __get_method(self):
    method = self.__method_root
    for i in self.method_path:
      method = getattr(method, i)
    self.__method = method.invoke

  def invoke_method(self, path):
    result = None
    error = None
    try:
      self.__get_method_path(path, self.body)
      self.__get_method()
      result = self.__method(self, self.parameters)
    except TotoException as e:
      logging.error("TotoException: %s Value: %s" % (e.code, e.value))
      error = e.__dict__
    except Exception as e:
      e = TotoException(ERROR_SERVER, str(e))
      logging.error("TotoException: %s Value: %s" % (e.code, e.value))
      error = e.__dict__
    return result, error

  """
    Request handlers
  """

  def options(self, path=None):
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
  def get(self, path=None):
    self.parameters = {}
    # Convert parameters with one item to string, will cause undesired behavior if user means to pass array with length 1
    for k, v in self.request.arguments.items():
      if len(v) == 1:
        self.parameters[k] = v[0]
      else:
        self.parameters[k] = v
    self.process_request(path)

  @tornado.web.asynchronous
  def post(self, path=None):
    if self.bson and 'content-type' in headers and headers['content-type'] == 'application/bson':
      self.response_type = 'application/bson'
      self.body = self.bson(self.request.body).decode()
    else:
      self.body = json.loads(self.request.body)
    self.parameters = 'parameters' in self.body and self.body['parameters'] or None
    self.process_request(path)

  def process_request(self, path=None):
    self.session = None
    self.__method = None
    self.add_header('access-control-allow-origin', self.ACCESS_CONTROL_ALLOW_ORIGIN)
    self.add_header('access-control-expose-headers', 'x-toto-hmac')
    (result, error) = self.invoke_method(path)
    if result is not None or error:
      self.respond(result, error, True)
    elif not self._finished and not hasattr(self.__method, 'asynchronous'):
      self.finish()

  """
    End request handlers
  """

  def respond(self, result=None, error=None, finish=True):
    if self._finished:
      return
    response = {}
    if result is not None:
      response['result'] = result
    if error:
      response['error'] = error
    self.add_header('content-type', self.response_type)
    if self.response_type == 'application/bson':
      response_body = str(self.bson.encode(response))
    else:
      response_body = json.dumps(response)
    if self.session:
      self.add_header('x-toto-hmac', base64.b64encode(hmac.new(str(self.session.user_id), response_body, hashlib.sha1).digest()))
    self.write(response_body)
    if finish:
      self.finish()

  def on_connection_close(self):
    if hasattr(self.__method, 'on_connection_close'):
      self.__method.on_connection_close(self);

  def register_event_handler(self, event_name, handler, run_on_main_loop=True):
    EventManager.instance().register_handler(event_name, handler, run_on_main_loop, self)

  def create_session(self, user_id, password, ttl=0):
    self.session = self.connection.create_session(user_id, password, ttl)
    return self.session

  def retrieve_session(self):
    headers = self.request.headers
    if 'x-toto-session-id' in headers:
      self.session = self.connection.retrieve_session(headers['x-toto-session-id'], 'x-toto-hmac' in headers and headers['x-toto-hmac'] or None, self.request.body)
    return self.session
    

