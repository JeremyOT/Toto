from toto.invocation import *
from toto.tasks import TaskQueue
from time import sleep

@asynchronous
def invoke(handler, parameters):
  def respond(params):
    sleep(0.1)
    handler.respond({'parameters': parameters})
  TaskQueue.instance('test').add_task(respond, parameters)
