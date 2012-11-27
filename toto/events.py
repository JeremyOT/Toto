'''Toto's event framework is used to allow external events to affect client requests, or to run scheduled tasks
after a specified signal is received. It can be used to send messages to active requests, even between multiple
server processes. The event framework can also be used outside of Toto to send messages to running Toto servers.
'''

import cPickle as pickle
from threading import Thread
from collections import deque
from tornado.web import *
from tornado.ioloop import IOLoop
from traceback import format_exc
from tornado.options import options
import zmq
import logging
import zlib
from random import choice, shuffle

class EventManager():
  '''Instances will listen on ``address`` for incoming events.
  '''

  def __init__(self, address=None):
    self.__handlers = {}
    self.address = address
    self.__zmq_context = zmq.Context()
    self.__remote_servers = {}
    self.__thread = None
    self.__queued_servers = deque()
  
  def register_server(self, address):
    '''Add a server located at ``address``. This server will now be included in the
    recipient list whenever ``send()`` is called.
    '''
    if address in self.__remote_servers:
      raise Exception('Server already registered: %s', address)
    socket = self.__zmq_context.socket(zmq.PUSH)
    socket.connect(address)
    self.__remote_servers[address] = socket
    self.refresh_server_queue()

  def remove_server(self, address):
    '''Remove the server located at ``address`` from the recipient list for all
    future calls to ``send()``.
    '''
    del self.__remote_servers[address]
    self.refresh_server_queue()
    
  def remove_all_servers(self):
    '''Clear the recipient list for all future calls to ``send``.
    '''
    self.__remote_servers.clear()
    self.refresh_server_queue()

  def refresh_server_queue(self):
    '''Reload and shuffle the registered server queue used for round-robin load
    balancing of non-broadcast events.
    '''
    self.__queued_servers.clear()
    self.__queued_servers.extend(self.__remote_servers.itervalues())
    shuffle(self.__queued_servers)
  
  def register_handler(self, event_name, event_handler, run_on_main_loop=False, request_handler=None, persist=False):
    '''Register ``event_handler`` to run when ``event_name`` is received. Handlers are meant to respond to
    a single event matching ``event_name`` only. If ``run_on_main_loop`` is ``True`` the handler will be executed
    on Tornado's main ``IOLoop`` (required if the handler will write to a response stream). If ``request_handler``
    is set, ``event_handler`` will not fire once ``request_handler`` has finished. Set ``persist`` to ``True``
    to automatically requeue ``event_handler`` each time it is executed.
    '''
    if not event_name in self.__handlers:
      self.__handlers[event_name] = set()
    handler_tuple = (event_handler, run_on_main_loop, request_handler, persist)
    self.__handlers[event_name].add(handler_tuple)
    return (event_name, handler_tuple)

  def remove_handler(self, handler_sig):
    '''Disable and remove the handler matching ``handler_sig``.
    '''
    self.__handlers[handler_sig[0]].discard(handler_sig[1])
  
  def start_listening(self):
    '''Starts listening for incoming events on ``EventManager.address``.
    '''
    if self.__thread:
      return
    def receive():
      context = zmq.Context()
      socket = context.socket(zmq.PULL)
      socket.bind(self.address)
      while True:
        event = pickle.loads(zlib.decompress(socket.recv()))
        event_name = event['name']
        event_args = event['args']
        if event_name in self.__handlers:
          handlers = self.__handlers[event_name]
          for handler in list(handlers):
            if not handler[3]:
              handlers.remove(handler)
            try:
              if handler[2] and handler[2]._finished:
                continue
              if handler[1]:
                (lambda h: IOLoop.instance().add_callback(lambda: h[0](event_args)))(handler)
              else:
                handler[0](event_args)
            except Exception as e:
              logging.error(format_exc())
    self.__thread = Thread(target=receive)
    self.__thread.daemon = True
    self.__thread.start()
  
  def send_to_server(self, address, event_name, event_args):
    '''Send a message with ``event_name`` and ``event_args`` only
    to the server listening at ``address``. ``address`` must have
    previously been passed to ``register_server``. This is more
    efficient than ``send`` if you only intent to send the event
    to a single server and know the address in advance.
    '''
    event = {'name': event_name, 'args': event_args}
    event_data = zlib.compress(pickle.dumps(event))
    self.__remote_servers[address].send(event_data)
  
  def send(self, event_name, event_args, broadcast=True):
    '''Send a message with ``event_name`` and ``event_args`` to
    all servers previously registered with ``register_server()``.
    If ``broadcast`` is false, the event will be sent to only
    a single server. Non-broadcast events are round-robin load
    balanced between registered servers.
    '''
    if not self.__remote_servers:
      return
    event = {'name': event_name, 'args': event_args}
    event_data = zlib.compress(pickle.dumps(event))
    if not broadcast:
      self.__queued_servers[0].send(event_data)
      self.__queued_servers.rotate(-1)
      return
    for socket in self.__queued_servers:
      socket.send(event_data)

  @classmethod
  def instance(cls):
    '''Returns the shared instance of ``EventManager``, instantiating on the first call.
    '''
    if not hasattr(cls, '_instance'):
      cls._instance = cls()
    return cls._instance
