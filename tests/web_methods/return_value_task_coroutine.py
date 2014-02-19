from toto.invocation import *
from toto.tasks import TaskQueue
from time import sleep
from tornado.gen import coroutine, Return, Task, Callback, Wait

@coroutine
def invoke(handler, parameters):
  def respond(params):
    sleep(0.1)
    return {'parameters': parameters}
  def return_true():
    sleep(0.1)
    return True

  response = TaskQueue.instance('test1').yield_task(respond, parameters)
  value = TaskQueue.instance('test2').yield_task(return_true)
  raise Return((yield value) and (yield response))
  
