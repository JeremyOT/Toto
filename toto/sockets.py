from tornado.web import *
import json
from invocation import *
from exceptions import *
from tornado.options import define, options
from events import EventManager
from tornado.websocket import WebSocketHandler
import logging

class TotoSocketHandler(WebSocketHandler):

  @classmethod
  def configure(cls):
    if options.debug:
      import traceback
      def log_error(self, e): 
        logging.error('%s\nHeaders: %s\n' % (traceback.format_exc(), repr(self.request.headers)))
      cls.log_error = log_error
    open_function = options.socket_opened_method and options.socket_opened_method.rsplit('.', 1)
    cls._on_open = open_function and getattr(__import__(open_function[0]), open_function[1]) or None
    closed_function = options.socket_closed_method and options.socket_closed_method.rsplit('.', 1)
    cls._on_close = closed_function and getattr(__import__(closed_function[0]), closed_function[1]) or None
    cls.__method = __import__(options.socket_method_module)

  def initialize(self, db_connection):
    self.db_connection = db_connection
    self.db = self.db_connection.db
    self.session = None
    self.registered_event_handlers = []

  def log_error(self, e):
    if isinstance(exception , TotoException):
      logging.error("TotoException: %s Value: %s" % (e.code, e.value))
    else:
      logging.error("TotoException: %s Value: %s" % (ERROR_SERVER, repr(e)))
  
  def create_session(self, user_id=None, password=None):
    self.session = self.db_connection.create_session(user_id, password)
    return self.session

  def retrieve_session(self, session_id):
      self.session = self.db_connection.retrieve_session(session_id, None, None)
      return self.session

  def open(self, session_id=None):
    if session_id:
      self.retrieve_session(session_id)
    if(self._on_open):
      self._on_open()

  def on_message(self, message_data):
    method = self.__method
    try:
      message = json.loads(message_data)
      for i in message['method'].split('.'):
        method = getattr(method, i)
      method.invoke(self, message['parameters'])
    except Exception as e:
      self.log_error(e)

  def send_message(self, data, message_id=None):
    self.write_message(message_id and {'message_id': message_id, 'data': data} or data)

  def register_event_handler(self, event_name, handler, run_on_main_loop=True, deregister_on_finish=False):
    sig = EventManager.instance().register_handler(event_name, handler, run_on_main_loop, self)
    if deregister_on_finish:
      self.registered_event_handlers.append(sig)
    return sig

  def deregister_event_handler(self, sig):
    EventManager.instance().remove_handler(sig)
    self.registered_event_handlers.remove(sig)

  def on_close(self):
    while self.registered_event_handlers:
      self.deregister_event_handler(self.registered_event_handlers[0])
    if(self._on_close):
      self._on_close()
