import toto
from toto.invocation import *
from toto.events import EventManager
from tornado.ioloop import IOLoop

@asynchronous
def invoke(handler, params):
  def receive_message(message):
    handler.respond(result={'message': message})
  EventManager.instance().register_handler("message", receive_message)
