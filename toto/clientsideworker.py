from tornado.web import *
import json
from invocation import *
from exceptions import *
from tornado.options import define, options
from events import EventManager
from tornado.websocket import WebSocketHandler
import logging
from collections import deque

class ClientSideWorkerManager(object):
  
  def __init__(self):
    self.__workers = {}
    self.__worker_queue = deque()
    self.__operation_queue = deque()
    self.__operation_callbacks = {}

  def add_worker(self, worker):
    self.__workers[id(worker)] = worker
    self.__worker_queue.append(id(worker))
    self.run_operation()

  def remove_worker(self, worker):
    del self.__workers[id(worker)]

  def run_operation(self):
    while self.__operation_queue and self.__worker_queue:
      operation = self.__operation_queue.popleft()
      worker_id = self.__worker_queue.popleft()
      self.__workers[worker_id].write_message({'operation_id': operation[0], 'script': operation[1]})
      if (operation[2]):
        self.__operation_queue.append(operation)

  def add_operation(self, operation_id, operation_script, callback_method=None, max_nodes=1, continuous=False):
    nodes = min(max_nodes, len(self.__worker_queue)) or 1
    if callback_method:
      self.__operation_callbacks[operation_id] = callback_method
    for i in xrange(nodes):
      self.__operation_queue.append((operation_id, operation_script, continuous))
    self.run_operation()

  def finish_operation(self, worker, operation_id, result):
    self.__worker_queue.append(id(worker))
    if operation_id in self.__operation_callbacks:
      self.__operation_callbacks[operation_id](worker, result)
    self.run_operation()

  @staticmethod
  def instance():
    if not hasattr(ClientSideWorkerManager, '_instance'):
      ClientSideWorkerManager._instance = ClientSideWorkerManager()
    return ClientSideWorkerManager._instance

# These methods allow ClientSideWorkerSocketHandler to be swapped with the bulkier TotoSocketHandler
def worker_connected(worker):
  ClientSideWorkerManager.instance().add_worker(worker)

def worker_disconnected(worker):
  ClientSideWorkerManager.instance().remove_worker(worker)

def complete(worker, data):
  ClientSideWorkerManager.instance().finish_operation(worker, data['operation_id'], data['result'])

class ClientSideWorkerSocketHandler(WebSocketHandler):

  @classmethod
  def configure(cls):
    if options.debug:
      import traceback
      def log_error(self, e): 
        logging.error('%s\nHeaders: %s\n' % (traceback.format_exc(), repr(self.request.headers)))
      cls.log_error = log_error

  def log_error(self, e):
    if isinstance(exception , TotoException):
      logging.error("TotoException: %s Value: %s" % (e.code, e.value))
    else:
      logging.error("TotoException: %s Value: %s" % (ERROR_SERVER, repr(e)))

  def open(self):
    ClientSideWorkerManager.instance().add_worker(self)

  def on_message(self, message_data):
    message = json.loads(message_data)
    ClientSideWorkerManager.instance().finish_operation(self, message['operation_id'], message['result'])

  def on_close(self):
    ClientSideWorkerManager.instance().remove_worker(self)
