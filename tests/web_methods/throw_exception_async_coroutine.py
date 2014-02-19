from toto.invocation import *
from time import sleep
from threading import Thread
from tornado.gen import coroutine, Return, Task

@coroutine
def invoke(handler, parameters):
  raise Exception('Test Exception')
