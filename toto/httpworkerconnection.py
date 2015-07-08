import toto
import cPickle as pickle
import zlib
import logging
from toto.exceptions import *
from toto.workerconnection import WorkerConnection
from threading import Thread, Lock
from tornado.options import options
from tornado.gen import coroutine, Return
from tornado.ioloop import IOLoop
from collections import deque
from tornado.httpclient import HTTPRequest, AsyncHTTPClient, HTTPError
from tornado.concurrent import Future
from sys import exc_info
from time import time
from uuid import uuid4
from traceback import format_exc
from toto.options import safe_define
from random import shuffle

class _Request(object):
  def __init__(self, headers, body, timeout, retry_count, future, callback=None):
    self.headers = headers
    self.body = body
    self.timeout = timeout
    self.retry_count = retry_count
    self.callback = callback
    self.future = future
    self.request_id = uuid4()

  def request(self, url):
    return HTTPRequest(url=url, method='POST', headers=self.headers, body=self.body)

  def handle_response(self, response):
    self.callback(self, response)

  def run_request(self, url):
    client = AsyncHTTPClient()
    client.fetch(self.request(url), callback=self.handle_response, raise_error=False)

class HTTPWorkerConnection(WorkerConnection):
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

     Pass ``serialization_mime`` to set the ``Content-Type`` header for worker requests.

     Use ``auto_retry_count`` to specify whether or not messages should be retried by default. Retrying messages can cause substantial
     congestion in your worker service. Use with caution.
  '''

  def __init__(self, address, timeout=10.0, compression=None, serialization=None, serialization_mime='application/pickle', auto_retry_count=0):
    if not address:
      self.active_connections = set()
    elif isinstance(address, str):
      self.active_connections = {i.strip() for i in address.split(',')}
    else:
      self.active_connections = set(address)
    self.__update_addresses()
    self.__connection_lock = Lock()
    self.__active_requests = {}
    self.mime = serialization_mime
    self.auto_retry_count = auto_retry_count
    self.timeout = timeout
    self.loads = serialization and serialization.loads or pickle.loads
    self.dumps = serialization and serialization.dumps or pickle.dumps
    self.compress = compression and compression.compress or (lambda x: x)
    self.decompress = compression and compression.decompress or (lambda x: x)

  def handle_response(self, request, response):
    if request.request_id not in self.__active_requests:
      logging.info("Received response for unknown request %s - it has likely already been answered." % request.request_id)
      return
    try:
      del(self.__active_requests[request.request_id])
      if response.error:
        if isinstance(response.error, HTTPError):
          if response.error.code == 599: #tornado special
            request.future.set_exception(response.error)
          else:
            request.future.set_result(self.loads(response.body))
        else:
          request.future.set_exception(response.error)
        return
      request.future.set_result(self.loads(response.body))
    except Exception as e:
      self.log_error(e)
      request.future.set_exc_info(exc_info())

  def handle_timeout(self, request):
    if request.request_id not in self.__active_requests:
      return #answered
    if request.retry_count <= 0:
      request.future.set_exception(TotoException(-1, "Timeout"))
      return
    request.retry_count -= 1
    request.run_request(self.__next_endpoint())
    if request.retry_count and request.timeout:
      IOLoop.current().add_timeout(time() + request.timeout, self.handle_timeout, request)

  @coroutine
  def invoke(self, method, parameters={}, callback=None, timeout=None, auto_retry_count=None, **kwargs):
    '''Invoke a ``method`` to be run on a remote worker process with the given ``parameters``. If specified, ``callback`` will be
       invoked with any response from the remote worker. By default the worker will timeout or retry based on the settings of the
       current ``WorkerConnection`` but ``timeout`` and ``auto_retry_count`` can be used for invocation specific behavior.

       ``invoke()`` returns a future that may be used to yield the result.

       Note: ``callback`` will be invoked with ``{'error': 'timeout'}`` on ``timeout`` if ``auto_retry`` is false. Invocations
       set to retry will never timeout and will instead be re-sent until a response is received. This behavior can be useful for
       critical operations but has the potential to cause substantial congestion in the worker system. Use with caution. Negative
       values of ``timeout`` will prevent messages from ever expiring or retrying regardless of ``auto_retry``. The default
       values of ``timeout`` and ``auto_retry`` cause a fallback to the values used to initialize ``WorkerConnection``.

       Alternatively, you can invoke methods with ``WorkerConnection.<module>.<method>(*args, **kwargs)``
       where ``"<module>.<method>"`` will be passed as the ``method`` argument to ``invoke()``.
    '''

    headers = {'Content-Type': self.mime}
    body = self.compress(self.dumps({'method': method, 'parameters': parameters}))
    timeout = timeout if timeout is not None else self.timeout
    auto_retry_count = auto_retry_count if auto_retry_count is not None else self.auto_retry_count
    future = Future()
    request = _Request(headers, body, timeout, auto_retry_count, future, self.handle_response)

    self.__active_requests[request.request_id] = request
    request.run_request(self.__next_endpoint())
    if auto_retry_count and timeout:
      IOLoop.current().add_timeout(time() + timeout, self.handle_timeout, request)

    result = yield future
    if callback:
      callback(result)
    raise Return(result)

  def __update_addresses(self):
    ordered_connections = list(self.active_connections)
    shuffle(ordered_connections)
    self.ordered_connections = ordered_connections
    self.next_connection_index = 0

  def add_connection(self, address):
    '''Connect to the worker at ``address``. Worker invocations will be round robin load balanced between all connected workers.'''
    with self.__connection_lock:
      self.active_connections.add(address)
      self.__update_addresses()

  def remove_connection(self, address):
    '''Disconnect from the worker at ``address``. Worker invocations will be round robin load balanced between all connected workers.'''
    with self.__connection_lock:
      self.active_connections.remove(address)
      self.__update_addresses()

  def set_connections(self, addresses):
    '''A convenience method to set the connected addresses. A connection will be made to any new address included in the ``addresses``
       enumerable and any currently connected address not included in ``addresses`` will be disconnected. If an address in ``addresses``
       is already connected, it will not be affected.
    '''
    with self.__connection_lock:
      self.active_connections = set(addresses)
      self.__update_addresses()

  def __next_endpoint(self):
    with self.__connection_lock:
      if self.next_connection_index >= len(self.ordered_connections):
        raise TotoException(-1, "No active connections")
      connection = self.ordered_connections[self.next_connection_index]
      self.next_connection_index += 1
      if self.next_connection_index >= len(self.ordered_connections):
        self.next_connection_index = 0
      return connection

  def __len__(self):
    return len(self.__active_requests)

  @classmethod
  def instance(cls):
    '''Returns the default instance of ``HTTPWorkerConnection`` as configured by the options prefixed
      with ``worker_``, instantiating it if necessary. Import the ``workerconnection`` module within
      your ``TotoService`` and run it with ``--help`` to see all available options.
    '''
    if not hasattr(cls, '_instance'):
      cls._instance = cls(options.worker_address, timeout=options.worker_timeout, compression=options.worker_compression_module and __import__(options.worker_compression_module), serialization=options.worker_serialization_module and __import__(options.worker_serialization_module), serialization_mime=options.worker_serialization_mime, auto_retry_count=options.worker_retry_count)
    return cls._instance
