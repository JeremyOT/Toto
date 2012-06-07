import cPickle as pickle
from urllib2 import Request, urlopen
from threading import Thread
from collections import deque
from tornado.web import *
from tornado.ioloop import IOLoop
from traceback import format_exc
from tornado.options import options
import logging

_private_event_key = ''
_server_routes = []
_local_route = ''

def _generate_key():
  import os
  from base64 import b64encode
  return b64encode(os.urandom(128))

def set_key(key):
  global _private_event_key
  _private_event_key = key or _generate_key()

def set_local_route(route):
  global _local_route
  _local_route = route

def add_route(route):
  _server_routes.append(route)

class EventHandler(RequestHandler):
  
  SUPPORTED_METHODS = ["POST",]
  
  def post(self):
    if _private_event_key and not ('x-toto-event-key' in self.request.headers and self.request.headers['x-toto-event-key'] == _private_event_key):
      raise HttpError(400, "Bad Request")
    event = pickle.loads(self.request.body)
    EventManager.instance().receive(event)

class EventManager():

  def __init__(self):
    self.__handlers = {}

  def remove_handler(self, handler_sig):
    self.__handlers[handler_sig[0]].discard(handler_sig[1])
  
  def register_handler(self, event_name, event_handler, run_on_main_loop=False, request_handler=None, persist=False):
    if not event_name in self.__handlers:
      self.__handlers[event_name] = set()
    handler_tuple = (event_handler, run_on_main_loop, request_handler, persist)
    self.__handlers[event_name].add(handler_tuple)
    return (event_name, handler_tuple)

  def receive(self, event):
    event_name = event['name']
    event_args = event['args']
    def event_thread():
      handlers = self.__handlers[event_name]
      persistent_handlers = set()
      while handlers:
        handler = handlers.pop()
        if handler[2] and handler[2]._finished:
          continue
        if handler[1]:
          handler[0](event_args)
        else:
          IOLoop.instance().add_callback(lambda: handler[0](event_args))
        if handler[3]:
          persistent_handlers.add(handler)
      handlers |= persistent_handlers
    if event_name in self.__handlers:
      Thread(target=event_thread).start()
  
  def send_to_route(self, route, event_name, event_args):
    event = {'name': event_name, 'args': event_args}
    event_data = pickle.dumps(event)
    urlopen(Request(route, event_data, {'x-toto-event-key': _private_event_key}))    
  
  def send(self, event_name, event_args):
    event = {'name': event_name, 'args': event_args}
    event_data = pickle.dumps(event)
    for route in _server_routes:
      if route == _local_route:
        self.receive(event)
      else:
        try:
          urlopen(Request(route, event_data, {'x-toto-event-key': _private_event_key}))
        except Exception as e:
          logging.error("Bad event route: %s - %s", route, options.debug and format_exc() or e)

  @staticmethod
  def instance():
    if not hasattr(EventManager, "_instance"):
      EventManager._instance = EventManager()
    return EventManager._instance
      
