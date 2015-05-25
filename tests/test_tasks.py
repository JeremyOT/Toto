import unittest

from uuid import uuid4
from time import time, sleep
from toto.tasks import TaskQueue, AwaitableInstance, InstancePool
from tornado.ioloop import IOLoop
from tornado.gen import coroutine

class _Instance(object):

  def __init__(self):
    self.counter = 0

  def increment(self):
    self.counter += 1
    return self.counter

  def value(self):
    return self.counter

class TestTasks(unittest.TestCase):

  def test_add_task(self):
    queue = TaskQueue()
    self.assertEquals(len(queue), 0)
    task_results = []
    task = lambda x: task_results.append(x)
    queue.add_task(task, 1)
    queue.add_task(task, 2)
    queue.add_task(task, 3)
    start = time()
    while 1:
      if len(task_results) == 3:
        break
      if time() - start > 5:
        break
      sleep(0.01)
    self.assertEquals(len(task_results), 3)
    self.assertEquals(task_results, [1, 2, 3])
  
  def test_yield_task(self):
    queue = TaskQueue()
    task_results = []
    @coroutine
    def yield_tasks():
      task = lambda x: x
      futures = []
      futures.append(queue.yield_task(task, 1))
      futures.append(queue.yield_task(task, 2))
      futures.append(queue.yield_task(task, 3))
      res = yield futures
      task_results[:] = res
    loop = IOLoop()
    loop.make_current()
    loop.run_sync(yield_tasks)
    self.assertEquals(len(task_results), 3)
    self.assertEquals(task_results, [1, 2, 3])

  def test_add_task_exception(self):
    queue = TaskQueue()
    self.assertEquals(len(queue), 0)
    task_results = []
    def task(x):
      task_results.append(x)
      raise Exception('failure')
    queue.add_task(task, 1)
    queue.add_task(task, 2)
    queue.add_task(task, 3)
    start = time()
    while 1:
      if len(task_results) == 3:
        break
      if time() - start > 5:
        break
      sleep(0.01)
    self.assertEquals(len(task_results), 3)
    self.assertEquals(task_results, [1, 2, 3])
  
  def test_yield_task_exception(self):
    queue = TaskQueue()
    task_results = []
    @coroutine
    def yield_tasks():
      def task(x):
        raise Exception('failure')
      futures = []
      futures.append(queue.yield_task(task, 1))
      futures.append(queue.yield_task(task, 2))
      futures.append(queue.yield_task(task, 3))
      for f in futures:
        try:
          yield f
        except Exception as e:
          task_results.append(e)
    loop = IOLoop()
    loop.make_current()
    loop.run_sync(yield_tasks)
    self.assertEquals(len(task_results), 3)
    for e in task_results:
      self.assertEquals(e.message, 'failure')

  def test_awaitable(self):
    instance = _Instance()
    instance.increment()
    self.assertEquals(instance.value(), 1)
    awaitable = AwaitableInstance(instance)
    @coroutine
    def yield_tasks():
      self.assertEquals((yield awaitable.increment()), 2)
      self.assertEquals((yield awaitable.increment()), 3)
      self.assertEquals((yield awaitable.increment()), 4)
      self.assertEquals((yield awaitable.value()), 4) 
    loop = IOLoop()
    loop.make_current()
    loop.run_sync(yield_tasks)
    self.assertEquals(instance.value(), 4)

  def test_instance_pool(self):
    instance1 = _Instance()
    instance2 = _Instance()
    pool = InstancePool([instance1, instance2])
    pool.increment()
    pool.increment()
    self.assertEquals(instance1.value(), 1)
    self.assertEquals(instance2.value(), 1)
    pool.transaction(lambda i: i.increment())
    pool.transaction(lambda i: i.increment())
    self.assertEquals(instance1.value(), 2)
    self.assertEquals(instance2.value(), 2)
    @coroutine
    def yield_tasks():
      self.assertEquals((yield pool.await().increment()), 3)
      self.assertEquals((yield pool.await().increment()), 3)
      self.assertEquals(instance1.value(), 3)
      self.assertEquals(instance2.value(), 3)
      self.assertEquals((yield pool.await_transaction(lambda i: i.increment())), 4)
      self.assertEquals((yield pool.await_transaction(lambda i: i.increment())), 4)
    loop = IOLoop()
    loop.make_current()
    loop.run_sync(yield_tasks)
    self.assertEquals(instance1.value(), 4)
    self.assertEquals(instance2.value(), 4)
