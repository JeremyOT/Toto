from toto.invocation import *
from toto.tasks import TaskQueue
from time import sleep
from tornado.gen import coroutine, Return, Task, Callback, Wait

@coroutine
def invoke(handler, parameters):
  def respond(params):
    sleep(0.1)
    raise Exception('Test Exception')
  raise Return((yield TaskQueue.instance('test1').yield_task(respond, parameters)))
  
