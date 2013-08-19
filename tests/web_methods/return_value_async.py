from toto.invocation import *
from time import sleep
from threading import Thread

@asynchronous
def invoke(handler, parameters):
  def respond():
    sleep(0.1)
    handler.respond({'parameters': parameters})
  Thread(target=respond).start()
