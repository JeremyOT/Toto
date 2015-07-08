import toto
import cPickle as pickle
import zlib
import logging
from threading import Thread
from tornado.options import options
from tornado.gen import Task
from collections import deque
from time import time
from uuid import uuid4
from traceback import format_exc
from toto.options import safe_define

safe_define("worker_compression_module", type=str, help="The module to use for compressing and decompressing messages to workers. The module must have 'decompress' and 'compress' methods. If not specified, no compression will be used. Only the default instance will be affected")
safe_define("worker_serialization_module", type=str, help="The module to use for serializing and deserializing messages to workers. The module must have 'dumps' and 'loads' methods. If not specified, cPickle will be used. Only the default instance will be affected")
safe_define("worker_serialization_mime", type=str, default='application/pickle', help="Used by HttpWorkerConnection in its Content-Type header.")
safe_define("worker_timeout", default=10.0, help="The default worker (instance()) will wait at least this many seconds before retrying a request (if retry is true), or timing out (if retry is false). Negative values will never retry or timeout. Note: This abs(value) is also the minimum resolution of any request-specific timeouts. Must not be 0.")
safe_define("worker_auto_retry", default=False, help="If True, the default timeout behavior of a worker RPC will be to retry instead of failing when the timeout is reached.")
safe_define("worker_retry_count", default=0, help="The maximum number of times to retry a request after timeout. Used by HttpWorkerConnection instead of worker_auto_retry.")
safe_define("worker_address", default='', help="This is the address that toto.workerconnection.invoke(method, params) will send tasks too (As specified in the worker conf file). A comma separated list may be used to round-robin load balance tasks between workers.")
safe_define("worker_transport", default='zmq', help="Either zmq or http to select which transport to use for worker communication.")

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

  def __getattr__(self, path):
    return WorkerInvocation(path, self)
  
  def log_error(self, error):
    logging.error(repr(error))

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
      if options.worker_transport == 'http':
        from toto.httpworkerconnection import HTTPWorkerConnection
        cls._instance = HTTPWorkerConnection.instance()
      else:
        from toto.zmqworkerconnection import ZMQWorkerConnection
        cls._instance = ZMQWorkerConnection.instance()
    return cls._instance

class WorkerInvocation(object):
  
  def __init__(self, path, connection):
    self._path = path
    self._connection = connection

  def __call__(self, *args, **kwargs):
    return self._connection.invoke(self._path, *args, **kwargs)

  def __getattr__(self, path):
    return getattr(self._connection, self._path + '.' + path)
