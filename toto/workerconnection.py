import toto
import zmq
import cPickle as pickle
import zlib
from tornado.options import options

class WorkerConnection(object):

  def __init__(self, address):
    self.address = address
    self.__context = zmq.Context()
    self.__socket = self.__context.socket(zmq.PUSH)
    self.__socket.connect(self.address)
  
  def invoke(self, method, parameters):
    self.__socket.send(zlib.compress(pickle.dumps({'method': method, 'parameters': parameters})))
  
  def __getattr__(self, path):
    return WorkerInvocation(path, self)

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
