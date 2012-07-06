import toto
import zmq
import cPickle as pickle
import zlib
import logging
from threading import Thread
from tornado.options import options, define
from collections import deque
from zmq.eventloop.ioloop import ZMQPoller, IOLoop, PeriodicCallback
from zmq.eventloop.zmqstream import ZMQStream
from time import time
from uuid import uuid4
from traceback import format_exc

define("worker_compression_module", type=str, help="The module to use for compressing and decompressing messages to workers. The module must have 'decompress' and 'compress' methods. If not specified, no compression will be used. Only the default instance will be affected")
define("worker_serialization_module", type=str, help="The module to use for serializing and deserializing messages to workers. The module must have 'dumps' and 'loads' methods. If not specified, cPickle will be used. Only the default instance will be affected")
define("worker_retry_ms", default=10000, help="The default worker (instance()) will wait at least this many milliseconds before retrying a request")

class WorkerConnection(object):

  def __init__(self, address, retry_ms=10000, compression=None, serialization=None):
    self.address = address
    self.message_address = 'inproc://WorkerConnection%s' % id(self)
    self.__context = zmq.Context()
    self.__queue_socket = self.__context.socket(zmq.PUSH)
    self.__queue_socket.bind(self.message_address)
    self.__thread = None
    self.__retry_ms = retry_ms
    self.__callbacks = {}
    self.__queued_messages = {}
    self.__message_timeouts = {}
    self.__ioloop = None
    self.loads = serialization and serialization.loads or pickle.loads
    self.dumps = serialization and serialization.dumps or pickle.dumps
    self.compress = compression and compression.compress or (lambda x: x)
    self.decompress = compression and compression.decompress or (lambda x: x)
  
  def invoke(self, method, parameters, callback=None, retry_ms=0):
    self._queue_message(self.compress(self.dumps({'method': method, 'parameters': parameters})), callback, retry_ms)
  
  def __len__(self):
    return len(self.__queued_messages)

  def __getattr__(self, path):
    return WorkerInvocation(path, self)

  def _queue_message(self, message, callback=None, retry_ms=0):
    if not self.__ioloop:
      self.start()
    message_id = str(uuid4())
    if callback:
      self.__callbacks[message_id] = callback
    if retry_ms > 0:
      self.__message_timeouts[message_id] = retry_ms
    self.__queue_socket.send_multipart(('', message_id, message))
  
  def log_error(self, error):
    logging.error(repr(e))

  def start(self):
    def loop():
      self.__ioloop = IOLoop()
      queue_socket = self.__context.socket(zmq.PULL)
      queue_socket.connect(self.message_address)
      queue_stream = ZMQStream(queue_socket, self.__ioloop)
      worker_socket = self.__context.socket(zmq.DEALER)
      worker_socket.connect(self.address)
      worker_stream = ZMQStream(worker_socket, self.__ioloop)

      def receive_response(message):
        self.__queued_messages.pop(message[1], None)
        self.__message_timeouts.pop(message[1], None)
        callback = self.__callbacks.pop(message[1], None)
        if callback:
          try:
            callback(self.loads(self.decompress(message[2])))
          except Exception as e:
            self.log_error(e)
      worker_stream.on_recv(receive_response)

      def queue_message(message):
        self.__queued_messages[message[1]] = (time() * 1000, message)
        try:
          worker_stream.send_multipart(message)
        except Exception as e:
          self.log_error(e)
      queue_stream.on_recv(queue_message)

      def requeue_message():
        now = time() * 1000
        for message in (item[1] for item in self.__queued_messages.itervalues() if item[0] + self.__message_timeouts.get(item[1][1], self.__retry_ms) < now):
          queue_message(message)
      requeue_callback = PeriodicCallback(requeue_message, self.__retry_ms, io_loop = self.__ioloop)
      requeue_callback.start()

      self.__ioloop.start()
      self.__thread = None
    self.__thread = Thread(target=loop)
    self.__thread.daemon = True
    self.__thread.start()

  def stop(self):
    if self.__ioloop:
      self.__ioloop.stop()
  
  def join(self):
    if self.__thread:
      self.__thread.join()

  def enable_traceback_logging(self):
    from new import instancemethod
    from traceback import format_exc
    def log_error(self, e):
      logging.error(format_exc)
    instancemethod(log_error, self)

  _instance = None
  @classmethod
  def instance(cls):
    if not cls._instance:
      cls._instance = cls(options.worker_address, retry_ms=options.worker_retry_ms, compression=options.worker_compression_module and __import__(options.worker_compression_module), serialization=options.worker_serialization_module and __import__(options.worker_serialization_module))
    return cls._instance

class WorkerInvocation(object):
  
  def __init__(self, path, connection):
    self._path = path
    self._connection = connection

  def __call__(self, parameters, callback=None, retry_ms=0):
    self._connection.invoke(self._path, parameters, callback, retry_ms)

  def __getattr__(self, path):
    return getattr(self._connection, self._path + '.' + path)
