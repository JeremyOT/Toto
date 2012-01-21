import toto
from toto.invocation import *
from toto.events import EventManager
from tornado.ioloop import IOLoop

@asynchronous
def invoke(handler, params):
  def receive_message(message):
    handler.write(message)
    handler.finish()
  EventManager.instance().register_handler("message", receive_message)
