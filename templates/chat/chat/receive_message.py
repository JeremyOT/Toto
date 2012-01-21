import toto
from toto.invocation import *
from toto.events import EventManager
from tornado.ioloop import IOLoop

@asynchronous
def invoke(handler, params):

  def receive_message(message):
    def write_message():
      handler.write(message)
      handler.finish()
    IOLoop.instance().add_callback(write_message)
  EventManager.instance().register_handler("message", receive_message)
