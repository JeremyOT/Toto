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

  def __init__(self, address=None):
    self.__handlers = {}
    self.address = address
    self.__zmq_context = zmq.Context()
    self.__remote_servers = {}
    self.__thread = None
    self.__queued_servers = deque()
  
  def register_server(self, address):
    if address in self.__remote_servers:
      raise Exception('Server already registered: %s', address)
    socket = self.__zmq_context.socket(zmq.PUSH)
    socket.connect(address)
    self.__remote_servers[address] = socket
    self.refresh_server_queue()

  def remove_server(self, address):
    del self.__remote_servers[address]
    self.refresh_server_queue()
    
  def remove_all_servers(self):
    self.__remote_servers.clear()
    self.refresh_server_queue()

  def refresh_server_queue(self):
    self.__queued_servers.clear()
    self.__queued_servers.extend(self.__remote_servers.itervalues())
    shuffle(self.__queued_servers)

  def remove_handler(self, handler_sig):
    self.__handlers[handler_sig[0]].discard(handler_sig[1])
  
  def register_handler(self, event_name, event_handler, run_on_main_loop=False, request_handler=None, persist=False):
    if not event_name in self.__handlers:
      self.__handlers[event_name] = set()
    handler_tuple = (event_handler, run_on_main_loop, request_handler, persist)
    self.__handlers[event_name].add(handler_tuple)
    return (event_name, handler_tuple)
  
  def start_listening(self):
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
          persistent_handlers = set()
          while handlers:
            handler = handlers.pop()
            try:
              if handler[2] and handler[2]._finished:
                continue
              if handler[1]:
                handler[0](event_args)
              else:
                IOLoop.instance().add_callback(lambda: handler[0](event_args))
            except Exception as e:
              logging.error(format_exc())
            if handler[3]:
              persistent_handlers.add(handler)
          handlers |= persistent_handlers
    self.__thread = Thread(target=receive)
    self.__thread.daemon = True
    self.__thread.start()
  
  def send_to_server(self, address, event_name, event_args):
    event = {'name': event_name, 'args': event_args}
    event_data = zlib.compress(pickle.dumps(event))
    self.__remote_servers[address].send(event_data)
  
  def send(self, event_name, event_args, broadcast=True):
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

  def start(self):
    def run():
      while(True):
        self.receive(pickle.loads(zlib.decompress(self.__socket.recv())))
        
    self.thread = threading.Thread()

  _instance = None
  @staticmethod
  def instance():
    if not EventManager._instance:
      EventManager._instance = EventManager()
    return EventManager._instance
