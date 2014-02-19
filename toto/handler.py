from tornado.web import *
import json
import hashlib
import hmac
from invocation import *
from exceptions import *
from tornado.options import define, options
import base64
from tornado.httputil import parse_multipart_form_data
from tornado.ioloop import IOLoop
from tornado.gen import coroutine, Return, engine
from tornado.concurrent import return_future, Future
import logging

define("allow_origin", default="*", help="This is the value for the Access-Control-Allow-Origin header (default *)")
define("method_select", default="both", metavar="both|url|parameter", help="Selects whether methods can be specified via URL, parameter in the message body or both (default both)")
define("bson_enabled", default=False, help="Allows requests to use BSON with content-type application/bson")
define("msgpack_enabled", default=False, help="Allows requests to use MessagePack with content-type application/msgpack")
define("hmac_enabled", default=True, help="Uses the x-toto-hmac header to verify authenticated requests.")

class BatchHandlerProxy(object):
  '''A proxy to a handler, this class intercepts calls to ``handler.respond()`` in order to match the
  response to the proper batch ``request_key``. If a method is invoked as part of a batch request,
  an instance of ``BatchHandlerProxy`` will be passed instead of a ``TotoHandler``. Though this
  replacement should be transparent to the method invocation, you may access the underlying handler
  with ``proxy.handler``.
  '''

  _non_proxy_keys = {'handler', 'request_key', 'async'}

  def __init__(self, handler, request_key):
    self.handler = handler
    self.request_key = request_key

  def __getattr__(self, attr):
    return getattr(self.handler, attr)

  def __setattr__(self, attr, value):
    if attr in self._non_proxy_keys:
      self.__dict__[attr] = value
    else:
      setattr(self.handler, attr, value)

  def respond(self, result=None, error=None, allow_async=True):
    '''Sets the response for the corresponding batch ``request_key``. When all requests have been processed,
    the combined response will passed to the underlying handler's ``respond()``.

    The ``allow_async`` parameter is for internal use only and is not intended to be supplied manually.
    '''
    #if the handler is processing an async method, schedule the response on the main runloop
    if self.async and allow_async:
      IOLoop.instance().add_callback(lambda: self.respond(result, error, False))
      return
    self.handler.batch_results[self.request_key] = error is not None and {'error': isinstance(error, dict) and error or self.handler.error_info(error)} or {'result': result}
    if len(self.handler.batch_results) == len(self.handler.request_keys):
      self.handler.respond(batch_results=self.handler.batch_results, allow_async=False)

class TotoHandler(RequestHandler):
  '''The handler is responsible for processing all requests to the server. An instance
  will be initialized for each incoming request and will handle authentication, session
  management and method delegation for you.
  
  You can set the module to use for method delegation via the ``method_module`` parameter.
  Methods are modules that contain an invoke function::

    def invoke(handler, parameters)
  
  The request handler will be passed as the first parameter to the invoke function and
  provides access to the server's database connection, the current session and other
  useful request properties. Request parameters will be passed as the second argument
  to the invoke function. Any return values from ``invoke()`` functions should be
  JSON serializable.
  
  Toto methods are generally invoked via a POST request to the server with a JSON
  serialized object as the body. The body should contain two properties:

  1. method - The name of the method to invoke.
  2. parameters - Any parameters to pass to the Toto function.

  For example::

    {"method": "account.create", "parameters": {"user_id": "test", "password": "testpassword"}}

  Will call method_module.account.create.invoke(handler, {'user_id': 'test', 'password': 'testpassword'})

  An ``invoke()`` function can be decorated with ``@tornado.gen.coroutine`` and be run as a Tornado coroutine.

  Alternatively, an ``invoke(handler, parameters)`` function may be decorated with ``@toto.invocation.asynchronous``.
  If a function decorated in this manner does not return a value, the connection well remain open until
  ``handler.respond(result, error)`` is called where ``error`` is an ``Exception`` or ``None`` and ``result``
  is a normal ``invoke()`` return value or ``None``.

  There are client libraries for iOS and Javascript that will make using Toto much easier. They are
  available at https://github.com/JeremyOT/TotoClient-iOS and https://github.com/JeremyOT/TotoClient-JS
  respectively.
  '''

  SUPPORTED_METHODS = {"POST", "OPTIONS", "GET", "HEAD"}
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
    self.headers_only = False
    self.async = False

  @classmethod
  def configure(cls):
    """Runtime method configuration.
    """
    #Method configuration
    if options.event_mode != 'off':
      from toto.events import EventManager
      cls.event_manager = EventManager
    if options.method_select == 'url':
      def get_method_path(self, path, body):
        if path:
          return '.'.join(path.split('/'))
        else:
          raise TotoException(ERROR_MISSING_METHOD, "Missing method.")
      cls.__get_method_path = get_method_path
    elif options.method_select == 'parameter':
      def get_method_path(self, path, body):
        if body and 'method' in body:
          logging.info(body['method'])
          return body['method']
        else:
          raise TotoException(ERROR_MISSING_METHOD, "Missing method.")
      cls.__get_method_path = get_method_path
    
    if options.use_cookies:
      import math
      set_cookie = options.secure_cookies and cls.set_secure_cookie or cls.set_cookie
      get_cookie = options.secure_cookies and cls.get_secure_cookie or cls.get_cookie
      def create_session(self, user_id=None, password=None, verify_password=True):
        self.session = self.db_connection.create_session(user_id, password, verify_password=verify_password)
        set_cookie(self, name='toto-session-id', value=self.session.session_id, expires_days=math.ceil(self.session.expires / (24.0 * 60.0 * 60.0)), domain=options.cookie_domain)
        return self.session
      cls.create_session = create_session
      
      def retrieve_session(self, session_id=None):
        if not self.session or (session_id and self.session.session_id != session_id):
          headers = self.request.headers
          if not session_id:
            session_id = 'x-toto-session-id' in headers and headers['x-toto-session-id'] or get_cookie(self, 'toto-session-id')
          if session_id:
            self.session = self.db_connection.retrieve_session(session_id, options.hmac_enabled and headers.get('x-toto-hmac'), options.hmac_enabled and 'x-toto-hmac' in headers and self.request.body or None)
        if self.session:
          set_cookie(self, name='toto-session-id', value=self.session.session_id, expires_days=math.ceil(self.session.expires / (24.0 * 60.0 * 60.0)), domain=options.cookie_domain)
        return self.session
      cls.retrieve_session = retrieve_session
    if options.debug:
      import traceback
      def error_info(self, e):
        if not isinstance(e, TotoException):
          e = TotoException(ERROR_SERVER, str(e))
        logging.error('%s\n%s\nHeaders: %s\n' % (e, traceback.format_exc(), repr(self.request.headers)))
        return e.__dict__
      cls.error_info = error_info
    cls.__method_root = __import__(options.method_module)
    cls.__method_cache = {}
      
  def __get_method_path(self, path, body):
    """The default method_select "both" (or any unsupported value) will
    call this method. The class method ``configure()`` will update this
    to a more efficient method according to ``tornado.options``.
    """
    if path:
      return '.'.join(path.split('/'))
    elif body and 'method' in body:
      logging.info(body['method'])
      return body['method']
    else:
      raise TotoException(ERROR_MISSING_METHOD, "Missing method.")

  def __get_method(self, path):
    try:
      return self.__method_cache[path]
    except KeyError:
      try:
        method = self.__method_root
        for component in path.split('.'):
          method = getattr(method, component)
        self.__method_cache[path] = method
      except AttributeError:
        raise TotoException(ERROR_INVALID_METHOD, "Cannot call '" + path + "'.")
    return self.__method_cache[path]

  def error_info(self, e):
    if not isinstance(e, TotoException):
      e = TotoException(ERROR_SERVER, str(e))
    logging.error("TotoException: %s Value: %s" % (e.code, e.value))
    return e.__dict__

  @coroutine
  def invoke_method(self, path, request_body, parameters, handler=None):
    result = None
    error = None
    method = None
    try:
      method = self.__get_method(self.__get_method_path(path, request_body))
      self.__active_methods.append(method)
      output = method.invoke(handler or self, parameters)
      if isinstance(output, Future):
        #result is a future, so yield the real response
        result = yield output
      else:
        result = output
    except Exception as e:
      error = self.error_info(e)
    raise Return((result, error, (hasattr(method, 'asynchronous'))))

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
  
  @coroutine
  def head(self, path=None):
    self.headers_only = True
    self.get(path)

  @coroutine
  def get(self, path=None):
    parameters = {}
    # Convert parameters with one item to string, will cause undesired behavior if user means to pass array with length 1
    for k, v in self.request.arguments.items():
      if len(v) == 1:
        parameters[k] = v[0]
      else:
        parameters[k] = v
    yield self.process_request(path, self.body, parameters)

  @coroutine
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
      yield self.batch_process_request(self.body['batch'])
    else:
      yield self.process_request(path, self.body, self.body and 'parameters' in self.body and self.body['parameters'] or {})
  
  @return_future
  @engine
  def batch_process_request(self, requests, callback):
    self._request_callback = callback
    self.session = None
    self.add_header('access-control-allow-origin', self.ACCESS_CONTROL_ALLOW_ORIGIN)
    self.add_header('access-control-expose-headers', 'x-toto-hmac')
    self.request_keys = sorted(requests.keys())
    self.batch_results = {}
    for k, v in ((i, requests[i]) for i in self.request_keys):
      proxy = BatchHandlerProxy(self, k)
      result, error, async = yield self.invoke_method(None, v, v.get('parameters', {}), handler=proxy)
      if async:
        proxy.async = True
      if result or error or not async:
        proxy.respond(result, error, allow_async=False)

  @return_future
  @engine 
  def process_request(self, path, request_body, parameters, callback):
    self._request_callback = callback
    self.session = None
    self.add_header('access-control-allow-origin', self.ACCESS_CONTROL_ALLOW_ORIGIN)
    self.add_header('access-control-expose-headers', 'x-toto-hmac')
    result, error, async = yield self.invoke_method(path, request_body, parameters)
    if async:
      self.async = True
    if result is not None or error:
      self.respond(result, error, allow_async=False)
    elif not async and not self._finished:
      self._request_callback()

  def respond(self, result=None, error=None, batch_results=None, allow_async=True):
    '''Respond to the request with the given result or error object (the ``batch_results`` and
    ``allow_async`` parameters are for internal use only and not intended to be supplied manually).
    Responses will be serialized according to the ``response_type`` propery. The default
    serialization is "application/json". Other supported protocols are:

    * application/bson - requires pymongo
    * application/msgpack - requires msgpack-python

    The response will also contain any available session information.
    
    To help with error handling in asynchronous methods, calling ``handler.respond(error=<your_error>)`` with a caught
    exception will trigger a normal Toto error response, log the error and finish the request. This is the same basic
    flow that is used internally when exceptions are raised from synchronous method calls.

    The "error" property of the response is derived from the ``error`` parameter in the following ways:

    1. If ``error`` is an instance of ``TotoException``, "error" will be a dictionary with "value" and "code" keys matching those of the ``TotoException``.
    2. In all other cases, ``error`` is first converted to a ``TotoException`` with ``code = <ERROR_SERVER>`` and ``value = str(error)`` before following (1.).

    To send custom error information, pass an instance of ``TotoException`` with ``value = <some_json_serializable_object>``.
    '''
    #if the handler is processing an async method, schedule the response on the main runloop
    if self.async and allow_async:
      IOLoop.instance().add_callback(lambda: self.respond(result, error, batch_results, False))
      return
    response = {}
    if result is not None:
      response['result'] = result
    if error:
      response['error'] = isinstance(error, dict) and error or self.error_info(error)
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
    if self.session and options.hmac_enabled:
      self.add_header('x-toto-hmac', base64.b64encode(hmac.new(str(self.session.user_id).lower(), response_body, hashlib.sha1).digest()))
    self.respond_raw(response_body, self.response_type)

  def respond_raw(self, body, content_type, finish=True):
    '''Respond raw is used by respond to send the response to the client. You can pass a string as the body parameter
    and it will be written directly to the response stream. The response "content-type" header will be set to ``content_type``.
    Use finish to specify whether or not the response stream should be closed after body is written. Use ``finish=False``
    to send the response in multiple calls to ``respond_raw``.
    '''
    self.add_header('content-type', content_type)
    if not self.headers_only:
      self.write(body)
    if finish:
      self._request_callback()

  def on_connection_close(self):
    '''You should not call this method directly, but if you implement an ``on_connection_close()`` function in a
    method module (where you defined invoke) it will be called when the connection closes if that method was
    invoked. E.G.::

      def invoke(handler, parameters):
        #main method body

      def on_connection_close(handler):
        #clean up
    '''
    for method in self.__active_methods:
      if hasattr(method, 'on_connection_close'):
        method.on_connection_close(self);
    self.on_finish()

  def register_event_handler(self, event_name, handler, run_on_main_loop=True, deregister_on_finish=False):
    '''If using Toto's event framework, this method makes it easy to register an event callback tied to the
    current connection and handler. Event handlers registered via this method will not be called once this handler
    has finished (connection closed). The ``deregister_on_finish`` parameter will cause this handler to be explicitly
    deregisted as part of the ``handler.on_finish`` event. Otherwise, event handlers are only cleaned up when the
    associated event is received.

    The return value can be used to manually deregister the event handler at a later point.
    '''
    sig = TotoHandler.event_manager.instance().register_handler(event_name, handler, run_on_main_loop, self)
    if deregister_on_finish:
      self.registered_event_handlers.append(sig)
    return sig

  def deregister_event_handler(self, sig):
    '''Pass the value returned from ``register_event_handler`` to deregister an active event handler.
    '''
    TotoHandler.event_manager.instance().remove_handler(sig)
    self.registered_event_handlers.remove(sig)

  def create_session(self, user_id=None, password=None, verify_password=True):
    '''Create a new session for the given user id and password (or an anonymous session if ``user_id`` is ``None``).
    After this method is called, the session will be available via ``self.session``. As with the
    ``db_connection.create_session()`` method, you may pass ``verify_password=False`` to create a session without
    checking the password. This can be used to implement alternative authentication methods like Facebook, Twitter
    and Google+.
    '''
    self.session = self.db_connection.create_session(user_id, password, verify_password)
    return self.session

  def retrieve_session(self, session_id=None):
    '''Retrieve the session specified by the request headers (or if enabled, the request cookie) and store it
    in ``self.session``. Alternatively, pass a ``session_id`` to this function to retrieve that session explicitly.
    '''
    if not self.session or (session_id and self.session.session_id != session_id):
      headers = self.request.headers
      if not session_id and 'x-toto-session-id' in headers:
        session_id = 'x-toto-session-id' in headers and headers['x-toto-session-id'] or None
      if session_id:
        self.session = self.db_connection.retrieve_session(session_id, options.hmac_enabled and headers.get('x-toto-hmac'), options.hmac_enabled and 'x-toto-hmac' in headers and self.request.body or None)
    return self.session
    
  def on_finish(self):
    while self.registered_event_handlers:
      self.deregister_event_handler(self.registered_event_handlers[0])

