import toto
import zmq
import cPickle as pickle
import zlib
import logging
from threading import Thread
from tornado.options import options
from tornado.gen import Task
from collections import deque
from zmq.eventloop.ioloop import ZMQPoller, IOLoop, PeriodicCallback
from zmq.eventloop.zmqstream import ZMQStream
from time import time
from uuid import uuid4
from traceback import format_exc
from toto.options import safe_define

safe_define("worker_compression_module", type=str, help="The module to use for compressing and decompressing messages to workers. The module must have 'decompress' and 'compress' methods. If not specified, no compression will be used. Only the default instance will be affected")
safe_define("worker_serialization_module", type=str, help="The module to use for serializing and deserializing messages to workers. The module must have 'dumps' and 'loads' methods. If not specified, cPickle will be used. Only the default instance will be affected")
safe_define("worker_timeout", default=10.0, help="The default worker (instance()) will wait at least this many seconds before retrying a request (if retry is true), or timing out (if retry is false). Negative values will never retry or timeout. Note: This abs(value) is also the minimum resolution of any request-specific timeouts. Must not be 0.")
safe_define("worker_auto_retry", default=False, help="If True, the default timeout behavior of a worker RPC will be to retry instead of failing when the timeout is reached.")
safe_define("worker_address", default='', help="This is the address that toto.workerconnection.invoke(method, params) will send tasks too (As specified in the worker conf file). A comma separated list may be used to round-robin load balance tasks between workers.")

WORKER_SOCKET_CONNECT = 'CONNECT'
WORKER_SOCKET_DISCONNECT = 'DISCONNECT'

class WorkerConnection(object):
  '''Use a ``WorkerConnection`` to make RPCs to the remote worker service(s) or worker/router specified by ``address``.
     ``address`` may be either an enumerable of address strings or a string of comma separated addresses. RPC retries
     and timeouts will happen by at most every ``abs(timeout)`` seconds when a periodic callback runs through all active
     messages and checks for prolonged requests. This is also the default timeout for any new calls. ``timeout`` must not be
     ``0``.

     Optionally pass any object or module with ``compress`` and ``decompress`` methods as the ``compression`` parameter to
     compress messages. The module must implement the same algorithm used on the worker service. By default, messages are not
     compressed.

     Optionally pass any object or module with ``dumps`` and ``loads`` methods that convert an ``object`` to and from a
     ``str`` to replace the default ``cPickle`` serialization with a protocol of your choice.

     Use ``auto_retry`` to specify whether or not messages should be retried by default. Retrying messages can cause substantial
     congestion in your worker service. Use with caution.
  '''

  def __init__(self, address, timeout=10.0, compression=None, serialization=None, auto_retry=False):
    if not address:
      self.active_connections = set()
    elif isinstance(address, str):
      self.active_connections = {i.strip() for i in address.split(',')}
    else:
      self.active_connections = set(address)
    self.message_address = 'inproc://WorkerConnection%s' % id(self)
    self.__context = zmq.Context()
    self.__queue_socket = self.__context.socket(zmq.PUSH)
    self.__queue_socket.bind(self.message_address)
    self.__thread = None
    self.__timeout = timeout
    self.__callbacks = {}
    self.__queued_messages = {}
    self.__message_auto_retry = {}
    self.__message_timeouts = {}
    self.__ioloop = None
    self.__auto_retry = auto_retry
    self.loads = serialization and serialization.loads or pickle.loads
    self.dumps = serialization and serialization.dumps or pickle.dumps
    self.compress = compression and compression.compress or (lambda x: x)
    self.decompress = compression and compression.decompress or (lambda x: x)

  def invoke(self, method, parameters={}, callback=None, timeout=0, auto_retry=None, await=False):
    '''Invoke a ``method`` to be run on a remote worker process with the given ``parameters``. If specified, ``callback`` will be
       invoked with any response from the remote worker. By default the worker will timeout or retry based on the settings of the
       current ``WorkerConnection`` but ``timeout`` and ``auto_retry`` can be used for invocation specific behavior.

       Note: ``callback`` will be invoked with ``{'error': 'timeout'}`` on ``timeout`` if ``auto_retry`` is false. Invocations
       set to retry will never timeout and will instead be re-sent until a response is received. This behavior can be useful for
       critical operations but has the potential to cause substantial congestion in the worker system. Use with caution. Negative
       values of ``timeout`` will prevent messages from ever expiring or retrying regardless of ``auto_retry``. The default
       values of ``timeout`` and ``auto_retry`` cause a fallback to the values used to initialize ``WorkerConnection``.

       Passing ``await=True`` will wrap the call in a ``tornado.gen.Task`` allowing you to ``yield`` the response from the worker.
       The ``Task`` replaces ``callback`` so any user supplied callback will be ignored when ``await=True``.

       Alternatively, you can invoke methods with ``WorkerConnection.<module>.<method>(*args, **kwargs)``
       where ``"<module>.<method>"`` will be passed as the ``method`` argument to ``invoke()``.
    '''
    if await:
      return Task(lambda callback: self._queue_message(self.compress(self.dumps({'method': method, 'parameters': parameters})), callback, timeout, auto_retry))
    self._queue_message(self.compress(self.dumps({'method': method, 'parameters': parameters})), callback, timeout, auto_retry)

  def add_connection(self, address):
    '''Connect to the worker at ``address``. Worker invocations will be round robin load balanced between all connected workers.'''
    self._queue_message(address, command=WORKER_SOCKET_CONNECT)

  def remove_connection(self, address):
    '''Disconnect from the worker at ``address``. Worker invocations will be round robin load balanced between all connected workers.'''
    self._queue_message(address, command=WORKER_SOCKET_DISCONNECT)

  def set_connections(self, addresses):
    '''A convenience method to set the connected addresses. A connection will be made to any new address included in the ``addresses``
       enumerable and any currently connected address not included in ``addresses`` will be disconnected. If an address in ``addresses``
       is already connected, it will not be affected.
    '''
    addresses = set(addresses)
    to_remove = self.active_connections - addresses
    to_add = addresses - self.active_connections
    for a in to_remove:
      self.remove_connection(a)
    for a in to_add:
      self.add_connection(a)

  def __len__(self):
    return len(self.__queued_messages)

  def __getattr__(self, path):
    return WorkerInvocation(path, self)

  def _queue_message(self, message, callback=None, timeout=0, auto_retry=None, command=''):
    if not self.__ioloop:
      self.start()
    message_id = str(uuid4())
    if callback:
      self.__callbacks[message_id] = callback
    if timeout != 0:
      self.__message_timeouts[message_id] = timeout
    if auto_retry is not None:
      self.__message_auto_retry[message_id] = auto_retry
    self.__queue_socket.send_multipart((command, message_id, message))
  
  def log_error(self, error):
    logging.error(repr(error))

  def start(self):
    if self.__ioloop:
      return
    def loop():
      self.__ioloop = IOLoop()
      queue_socket = self.__context.socket(zmq.PULL)
      queue_socket.connect(self.message_address)
      queue_stream = ZMQStream(queue_socket, self.__ioloop)

      def receive_response(message, response_override=None):
        self.__queued_messages.pop(message[1], None)
        self.__message_timeouts.pop(message[1], None)
        callback = self.__callbacks.pop(message[1], None)
        if callback:
          try:
            callback(response_override or self.loads(self.decompress(message[2])))
          except Exception as e:
            self.log_error(e)
            callback({'error': e})

      def create_worker_stream():
        def close_callback():
          logging.info('Worker stream closed')
          create_worker_stream()
        worker_socket = self.__context.socket(zmq.DEALER)
        for address in self.active_connections:
          worker_socket.connect(address)
        worker_stream = ZMQStream(worker_socket, self.__ioloop)
        worker_stream.on_recv(receive_response)
        worker_stream.set_close_callback(close_callback)
        self._worker_stream = worker_stream
      create_worker_stream()

      def queue_message(message):
        if message[0]:
          if message[0] == WORKER_SOCKET_CONNECT and message[2] not in self.active_connections:
            self.active_connections.add(message[2])
            self._worker_stream.socket.connect(message[2])
          elif message[0] == WORKER_SOCKET_DISCONNECT and message[2] in self.active_connections:
            self.active_connections.remove(message[2])
            self._worker_stream.socket.disconnect(message[2])
          return
        self.__queued_messages[message[1]] = (time(), message)
        try:
          self._worker_stream.send_multipart(message)
        except IOError as e:
          self.log_error(e)
          logging.info('Reconnecting')
          create_worker_stream()
        except Exception as e:
          self.log_error(e)
      queue_stream.on_recv(queue_message)

      def timeout_message():
        now = time()
        for message, retry in [(item[1], self.__message_auto_retry.get(item[1][1], self.__auto_retry)) for item, t in ((i, self.__message_timeouts.get(i[1][1], self.__timeout)) for i in self.__queued_messages.itervalues()) if t >= 0 and (item[0] + t < now)]:
          if retry:
            logging.info('Worker timeout, requeuing ' + message[1])
            queue_message(message)
          else:
            receive_response(('', message[1]), {'error': 'timeout'})
      timeout_callback = PeriodicCallback(timeout_message, int(abs(self.__timeout * 1000.0)), io_loop = self.__ioloop)
      timeout_callback.start()

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
      logging.error(format_exc())
    self.log_error = instancemethod(log_error, self)

  @classmethod
  def instance(cls):
    '''Returns the default instance of ``WorkerConnection`` as configured by the options prefixed
      with ``worker_``, instantiating it if necessary. Import the ``workerconnection`` module within
      your ``TotoService`` and run it with ``--help`` to see all available options.
    '''
    if not hasattr(cls, '_instance'):
      cls._instance = cls(options.worker_address, timeout=options.worker_timeout, compression=options.worker_compression_module and __import__(options.worker_compression_module), serialization=options.worker_serialization_module and __import__(options.worker_serialization_module), auto_retry=options.worker_auto_retry)
    return cls._instance

class WorkerInvocation(object):
  
  def __init__(self, path, connection):
    self._path = path
    self._connection = connection

  def __call__(self, *args, **kwargs):
    return self._connection.invoke(self._path, *args, **kwargs)

  def __getattr__(self, path):
    return getattr(self._connection, self._path + '.' + path)
