import toto
import zmq
import cPickle as pickle
import zlib
import logging
from threading import Thread
from tornado.options import options
from collections import deque

class WorkerConnection(object):

  def __init__(self, address):
    self.address = address
    self.__context = zmq.Context()
    self.__thread = None
    self.__queue = deque()
  
  def invoke(self, method, parameters):
    self.__queue_request(zlib.compress(pickle.dumps({'method': method, 'parameters': parameters})))
  
  def __len__(self):
    return len(self.__queue)

  def __getattr__(self, path):
    return WorkerInvocation(path, self)

  def __queue_request(self, request):
    self.__queue.append(request)
    if self.__thread:
      return
    def send_queue():
      socket = self.__context.socket(zmq.REQ)
      socket.connect(self.address)
      while self.__queue:
        try:
          socket.send(self.__queue[0])
          response = pickle.loads(zlib.decompress(socket.recv()))
          if response and response['received']:
            self.__queue.popleft()
        except Exception as e:
          logging.error(repr(e))
      self.__thread = None
    self.__thread = Thread(target=send_queue)
    self.__thread.daemon = True
    self.__thread.start()
  
  def join(self):
    if self.__thread:
      self.__thread.join()

  _instance = None
  @classmethod
  def instance(cls):
    if not cls._instance:
      cls._instance = cls(options.worker_address)
    return cls._instance

class WorkerInvocation(object):
  
  def __init__(self, path, connection):
    self.path = path
    self.connection = connection

  def __call__(self, parameters):
    self.connection.invoke(self.path, parameters)

  def __getattr__(self, path):
    return getattr(self.connection, self.path + '.' + path)
