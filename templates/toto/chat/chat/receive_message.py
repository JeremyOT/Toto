import toto
from toto.invocation import *
from tornado.ioloop import IOLoop

@asynchronous
def invoke(handler, params):
  def receive_message(message):
    handler.respond(result={'message': message})
  handler.register_event_handler('message', receive_message, deregister_on_finish=True)
