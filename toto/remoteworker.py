from tornado.web import *
import json
from invocation import *
from exceptions import *
from tornado.options import define, options
from events import EventManager
from tornado.websocket import WebSocketHandler
import logging
from collections import deque

class RemoteWorkerManager(object):
  
  def __init__(self):
    self.__workers = {}
    self.__worker_queue = deque()
    self.__operation_queue = deque()
    self.__operation_callbacks = {}

  def add_worker(self, worker):
    self.__workers(id(worker), worker)
    self.__worker_queue.append(id(worker))
    self.run_operation()

  def remove_worker(self, worker):
    del self.__workers[id(worker)]

  def run_operation(self):
    while self.__operation_queue and self.__worker_queue:
      operation = self.__operation_queue.popleft()
      worker_id = self.__worker_queue.popleft()
      self.__workers[worker_id].write_message({'operation_id': operation[0], 'script': operation[1]})

  def add_operation(self, operation_id, operation_script, callback_method=None, max_nodes=1):
    nodes = min(max_nodes, len(self.__worker_queue)) or 1
    if callback_method:
      self.__operation_callbacks[operation_id] = callback_method
    for i in xrange(nodes):
      self.__operation_queue.append((operation_id, operation_script))
    self.run_operation()

  def finish_operation(self, worker, operation_id, result):
    self.__worker_queue.append(id(worker))
    if operation_id in self.__operation_callbacks:
      self.__operation_callbacks[operation_id](worker, result)
    self.run_operation()

  @staticmethod
  def instance():
    if not hasattr(RemoteWorkerManager, '_instance'):
      RemoteWorkerManager._instance = RemoteWorkerManager()
    return RemoteWorkerManager._instance

class RemoteWorkerSocketHandler(WebSocketHandler):

  @classmethod
  def configure(cls):
    if options.debug:
      import traceback
      def log_error(self, e): 
        logging.error('%s\nHeaders: %s\n' % (traceback.format_exc(), repr(self.request.headers)))
      cls.log_error = log_error

  def initialize(self, method_root, connection, on_open, on_close):
    self.__method_root = method_root
    self.db_connection = connection
    self.__on_open = on_open
    self.__on_close = on_close
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

  def open(self):
    RemoteWorkerManager.instance().add_worker(self)

  def on_message(self, message_data):
    message = json.loads(message_data)
    RemoteWorkerManager.instance().finish_operation(self, message['operation_id'], message['result'])

  def on_close(self):
    RemoteWorkerManager.instance().remove_worker(self)
