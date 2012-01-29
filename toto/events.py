import cPickle as pickle
from urllib2 import Request, urlopen
from threading import Thread
from collections import deque
from tornado.web import *
from tornado.ioloop import IOLoop

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
  
  def register_handler(self, event_name, handler, run_on_main_loop=False, request_handler=None):
    if not event_name in self.__handlers:
      self.__handlers[event_name] = deque()
    self.__handlers[event_name].append((handler, run_on_main_loop, request_handler))

  def receive(self, event):
    event_name = event['name']
    event_args = event['args']
    def event_thread():
      handlers = self.__handlers[event_name]
      for i in xrange(len(handlers)):
        handler = handlers.popleft()
        if handler[2] and handler[2]._finished:
          continue
        if handler[1]:
          handler[0](event_args)
        else:
          IOLoop.instance().add_callback(lambda: handler[0](event_args))
    if event_name in self.__handlers:
      Thread(target=event_thread).start()
  
  def send(self, event_name, event_args):
    event = {'name': event_name, 'args': event_args}
    event_data = pickle.dumps(event)
    for route in _server_routes:
      if route == _local_route:
        self.receive(event)
      else:
        urlopen(Request(route, event_data, {'x-toto-event-key': _private_event_key}))

  @staticmethod
  def instance():
    if not hasattr(EventManager, "_instance"):
      EventManager._instance = EventManager()
    return EventManager._instance
      
