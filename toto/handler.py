from tornado.web import *
import json
import hashlib
import hmac
from invocation import *
from exceptions import *
from tornado.options import define, options
import base64
from tornado.httputil import parse_multipart_form_data
import logging

define("allow_origin", default="*", help="This is the value for the Access-Control-Allow-Origin header (default *)")
define("method_select", default="both", metavar="both|url|parameter", help="Selects whether methods can be specified via URL, parameter in the message body or both (default both)")
define("bson_enabled", default=False, help="Allows requests to use BSON with content-type application/bson")
define("msgpack_enabled", default=False, help="Allows requests to use MessagePack with content-type application/msgpack")

class TotoHandler(RequestHandler):

  SUPPORTED_METHODS = ["POST", "OPTIONS", "GET"]
  ACCESS_CONTROL_ALLOW_ORIGIN = options.allow_origin

  def initialize(self, db_connection):
    self.db_connection = db_connection
    self.db = self.db_connection.db
    self.bson = options.bson_enabled and __import__('bson').BSON
    self.msgpack = options.msgpack_enabled and __import__('msgpack')
    self.response_type = 'application/json'
    self.body = None
    self.registered_event_handlers = []
    self.__active_methods = []

  """
    Runtime method configuration
  """
  @classmethod
  def configure(cls):
    #Method configuration
    if options.event_mode != 'off':
      from toto.events import EventManager
      cls.event_manager = EventManager
    if options.method_select == 'url':
      def get_method_path(self, path, body):
        if path:
          return path.split('/')
        else:
          raise TotoException(ERROR_MISSING_METHOD, "Missing method.")
      cls.__get_method_path = get_method_path
    elif options.method_select == 'parameter':
      def get_method_path(self, path, body):
        if body and 'method' in body:
          return body['method'].split('.')
        else:
          raise TotoException(ERROR_MISSING_METHOD, "Missing method.")
      cls.__get_method_path = get_method_path
    
    if options.use_cookies:
      import math
      set_cookie = options.secure_cookies and cls.set_secure_cookie or cls.set_cookie
      get_cookie = options.secure_cookies and cls.get_secure_cookie or cls.get_cookie
      def create_session(self, user_id=None, password=None):
        self.session = self.db_connection.create_session(user_id, password)
        set_cookie(self, name='toto-session-id', value=self.session.session_id, expires_days=math.ceil(self.session.expires / (24.0 * 60.0 * 60.0)), domain=options.cookie_domain)
        return self.session
      cls.create_session = create_session
      
      def retrieve_session(self, session_id=None):
        if not self.session or (session_id and self.session.session_id != session_id):
          headers = self.request.headers
          if not session_id:
            session_id = 'x-toto-session-id' in headers and headers['x-toto-session-id'] or get_cookie(self, 'toto-session-id')
          if session_id:
            self.session = self.db_connection.retrieve_session(session_id, 'x-toto-hmac' in headers and headers['x-toto-hmac'] or None, 'x-toto-hmac' in headers and self.request.body or None)
        if self.session:
          set_cookie(self, name='toto-session-id', value=self.session.session_id, expires_days=math.ceil(self.session.expires / (24.0 * 60.0 * 60.0)), domain=options.cookie_domain)
        return self.session
      cls.retrieve_session = retrieve_session
    if options.debug:
      import traceback
      def error_info(self, e):
        if isinstance(e , TotoException):
          logging.error('%s\nHeaders: %s\n' % (traceback.format_exc(), repr(self.request.headers)))
          return e.__dict__
        else:
          logging.error('%s\nHeaders: %s\n' % (traceback.format_exc(), repr(self.request.headers)))
          return TotoException(ERROR_SERVER, repr(e)).__dict__
      cls.error_info = error_info
    cls.__method_root = __import__(options.method_module)
      
  """
    The default method_select "both" (or any unsupported value) will
    call this method. The class method configure() will update this
    to a more efficient method according to the tornado.options
  """
  def __get_method_path(self, path, body):
    if path:
      return path.split('/')
    elif body and 'method' in body:
      return body['method'].split('.')
    else:
      raise TotoException(ERROR_MISSING_METHOD, "Missing method.")

  def __get_method(self, path):
    method = self.__method_root
    for i in path:
      method = getattr(method, i)
    return method

  def error_info(self, e):
    if isinstance(e, TotoException):
      logging.error("TotoException: %s Value: %s" % (e.code, e.value))
      return e.__dict__
    else:
      e = TotoException(ERROR_SERVER, repr(e))
      logging.error("TotoException: %s Value: %s" % (e.code, e.value))
      return e.__dict__
      

  def invoke_method(self, path, request_body, parameters, finish_by_default=True):
    result = None
    error = None
    method = None
    try:
      method = self.__get_method(self.__get_method_path(path, request_body))
      self.__active_methods.append(method)
      result = method.invoke(self, parameters)
    except Exception as e:
      error = self.error_info(e)
    return result, error, (finish_by_default and not hasattr(method, 'asynchronous'))

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
    parameters = {}
    # Convert parameters with one item to string, will cause undesired behavior if user means to pass array with length 1
    for k, v in self.request.arguments.items():
      if len(v) == 1:
        parameters[k] = v[0]
      else:
        parameters[k] = v
    self.process_request(path, self.body, parameters)

  @tornado.web.asynchronous
  def post(self, path=None):
    content_type = 'content-type' in self.request.headers and self.request.headers['content-type'] or 'application/json'
    if not content_type.startswith('application/json'):
      if content_type.startswith('application/x-www-form-urlencoded'):
        self.body = {'parameters': self.request.arguments}
      elif content_type.startswith('multipart/form-data'):
        self.body = {'parameters': {'arguments': self.request.arguments, 'files': self.request.files}}
      elif self.bson and content_type.startswith('application/bson'):
        self.response_type = 'application/bson'
        self.body = self.bson(self.request.body).decode()
      elif self.msgpack and content_type.startswith('application/msgpack'):
        self.response_type = 'application/msgpack'
        self.body = self.msgpack.loads(self.request.body)
    else:
      self.body = json.loads(self.request.body)
    if self.body and 'batch' in self.body:
      self.batch_process_request(self.body['batch'])
    else:
      self.process_request(path, self.body, self.body and 'parameters' in self.body and self.body['parameters'] or {})
  
  def batch_process_request(self, requests):
    self.session = None
    self.add_header('access-control-allow-origin', self.ACCESS_CONTROL_ALLOW_ORIGIN)
    self.add_header('access-control-expose-headers', 'x-toto-hmac')
    batch_results = {}
    for k, v in requests.iteritems():
      (result, error, finish_by_default) = self.invoke_method(None, v, v['parameters'], False)
      batch_results[k] = error is not None and {'error': error} or {'result': result}
    self.respond(batch_results=batch_results)

  
  def process_request(self, path, request_body, parameters, finish_by_default=True):
    self.session = None
    self.add_header('access-control-allow-origin', self.ACCESS_CONTROL_ALLOW_ORIGIN)
    self.add_header('access-control-expose-headers', 'x-toto-hmac')
    (result, error, finish_by_default) = self.invoke_method(path, request_body, parameters, finish_by_default)
    if result is not None or error:
      self.respond(result, error)
    elif finish_by_default and not self._finished:
      self.finish()

  """
    End request handlers
  """

  def respond(self, result=None, error=None, batch_results=None):
    response = {}
    if result is not None:
      response['result'] = result
    if error:
      response['error'] = error
    if batch_results:
      response['batch'] = batch_results
    if self.session:
      response['session'] = {'session_id': self.session.session_id, 'expires': self.session.expires, 'user_id': str(self.session.user_id)}
    if self.response_type == 'application/bson':
      response_body = str(self.bson.encode(response))
    elif self.response_type == 'application/msgpack':
      response_body = self.msgpack.dumps(response)
    else:
      response_body = json.dumps(response)
    if self.session:
      self.add_header('x-toto-hmac', base64.b64encode(hmac.new(str(self.session.user_id).lower(), response_body, hashlib.sha1).digest()))
    self.respond_raw(response_body, self.response_type)

  def respond_raw(self, body, content_type, finish=True):
    self.add_header('content-type', content_type)
    self.write(body)
    if finish:
      self.finish()

  def on_connection_close(self):
    for method in self.__active_methods:
      if hasattr(method, 'on_connection_close'):
        method.on_connection_close(self);
    self.on_finish()

  def register_event_handler(self, event_name, handler, run_on_main_loop=True, deregister_on_finish=False):
    sig = TotoHandler.event_manager.instance().register_handler(event_name, handler, run_on_main_loop, self)
    if deregister_on_finish:
      self.registered_event_handlers.append(sig)
    return sig

  def deregister_event_handler(self, sig):
    TotoHandler.event_manager.instance().remove_handler(sig)
    self.registered_event_handlers.remove(sig)

  def create_session(self, user_id=None, password=None):
    self.session = self.db_connection.create_session(user_id, password)
    return self.session

  def retrieve_session(self, session_id=None):
    if not self.session or (session_id and self.session.session_id != session_id):
      headers = self.request.headers
      if not session_id and 'x-toto-session-id' in headers:
        session_id = 'x-toto-session-id' in headers and headers['x-toto-session-id'] or None
      if session_id:
        self.session = self.db_connection.retrieve_session(session_id, 'x-toto-hmac' in headers and headers['x-toto-hmac'] or None, self.request.body)
    return self.session
    
  def on_finish(self):
    while self.registered_event_handlers:
      self.deregister_event_handler(self.registered_event_handlers[0])

