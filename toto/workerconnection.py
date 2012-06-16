import toto
import zmq
import cPickle as pickle
import zlib
import logging
from threading import Thread
from tornado.options import options
from collections import deque
from zmq.eventloop.ioloop import ZMQPoller, IOLoop, PeriodicCallback
from zmq.eventloop.zmqstream import ZMQStream
from time import time
from uuid import uuid4
from traceback import format_exc

class WorkerConnection(object):

  def __init__(self, address, request_timeout_ms=5000):
    self.address = address
    self.message_address = 'inproc://WorkerConnection%s' % id(self)
    self.__context = zmq.Context()
    self.__queue_socket = self.__context.socket(zmq.PUSH)
    self.__queue_socket.bind(self.message_address)
    self.__thread = None
    self.__request_timeout_ms = request_timeout_ms
    self.__callbacks = {}
    self.__queued_messages = {}
    self.__ioloop = None
  
  def invoke(self, method, parameters, callback=None):
    self._queue_message(zlib.compress(pickle.dumps({'method': method, 'parameters': parameters})), callback)
  
  def __len__(self):
    return len(self.__queued_messages)

  def __getattr__(self, path):
    return WorkerInvocation(path, self)

  def _queue_message(self, message, callback=None):
    if not self.__ioloop:
      self.start()
    message_id = str(uuid4())
    if callback:
      self.__callbacks[message_id] = callback
    self.__queue_socket.send_multipart(('', message_id, message))

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
        callback = self.__callbacks.pop(message[1], None)
        if callback:
          try:
            callback(pickle.loads(zlib.decompress(message[1])))
          except Exception as e:
            logging.error(repr(e))
      worker_stream.on_recv(receive_response)

      def queue_message(message):
        self.__queued_messages[message[1]] = (time() * 1000, message)
        try:
          worker_stream.send_multipart(message)
        except Exception as e:
          logging.error(repr(e))
      queue_stream.on_recv(queue_message)

      def requeue_message():
        now = time() * 1000
        for message in (item[1] for item in self.__queued_messages.itervalues() if item[0] + self.__request_timeout_ms < now):
          queue_message(message)
      requeue_callback = PeriodicCallback(requeue_message, self.__request_timeout_ms, io_loop = self.__ioloop)
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

  _instance = None
  @classmethod
  def instance(cls):
    if not cls._instance:
      cls._instance = cls(options.worker_address)
    return cls._instance

class WorkerInvocation(object):
  
  def __init__(self, path, connection):
    self._path = path
    self._connection = connection

  def __call__(self, parameters):
    self._connection.invoke(self._path, parameters)

  def __getattr__(self, path):
    return getattr(self._connection, self._path + '.' + path)
