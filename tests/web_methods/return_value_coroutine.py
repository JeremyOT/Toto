from toto.invocation import *
from time import sleep
from threading import Thread
from tornado.gen import coroutine, Return, Task

@coroutine
def invoke(handler, parameters):
  def respond(callback):
    sleep(0.1)
    callback({'parameters': parameters})
  result = yield Task(lambda callback: Thread(target=respond, args=[callback]).start())
  raise Return(result)
