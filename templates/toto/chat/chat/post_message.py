import toto
from toto.invocation import *
from toto.events import EventManager

@requires("message")
def invoke(handler, params):
  EventManager.instance().send("message", params["message"])
  return "message sent!"
