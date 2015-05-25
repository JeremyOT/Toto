'''Toto provides build a built in task queue for performing work in the background
while limiting the number of active jobs. The task queue is designed primarily for
shorter, lightweight jobs. For CPU intensive tasks or tasks that are expected to
run for a long time, look at Toto's worker functionality instead.
'''
from threading import Thread, Lock, Condition
from collections import deque
from tornado.gen import coroutine, Return
from tornado.concurrent import Future
from tornado.ioloop import IOLoop
from Queue import Queue, Empty
from sys import exc_info
from itertools import count
import logging
import traceback

class TaskQueue():
  '''Instances will run up to ``thread_count`` tasks at a time
  whenever there are tasks in the queue. Theads will be killed
  if unused for longer than ``idle_timeout`` seconds.
  '''

  def __init__(self, thread_count=1, idle_timeout=60, name='TaskQueue'):
    self.tasks = deque()
    self.running = False
    self.condition = Condition()
    self.threads = set()
    self.idle_timeout = idle_timeout
    self.thread_count = thread_count
    self.name = name

  def add_task(self, fn, *args, **kwargs):
    '''Add the function ``fn`` to the queue to be invoked with
    ``args`` and ``kwargs`` as arguments. If the ``TaskQueue``
    is not currently running, it will be started now.
    '''
    with self.condition:
      self.tasks.append((fn, args, kwargs))
      self.condition.notify()
      self.run()

  def yield_task(self, fn, *args, **kwargs):
    '''Like add_task but will call the function as a coroutine, allowing you
    to yield the return value from within a function decorated with ``@tornado.gen.coroutine``
    or ``@tornado.gen.engine``.

    Usage::

      def add(arg1, arg2):
        return arg1 + arg2

      @tornado.gen.engine
      def caller():
        value = yield TaskQueue.instance('myqueue').yield_task(add, 1, 2)
        print value #prints 3

    '''

    ioloop = IOLoop.current()
    future = Future()
    def call():
      result = None
      error = None
      try:
        result = fn(*args, **kwargs)
      except Exception as e:
        ioloop.add_callback(future.set_exc_info, exc_info())
      else:
        # tornado future is not threadsafe
        ioloop.add_callback(future.set_result, result)
    self.add_task(call)
    return future

  def run(self):
    '''Start processing jobs in the queue. You should not need
    to call this as ``add_task`` automatically starts the queue.
    Processing threads will stop when there are no jobs available
    in the queue for at least ``idle_timeout`` seconds.
    '''
    with self.condition:
      if len(self.threads) >= self.thread_count:
        return
      thread = self.__TaskLoop(self)
      self.threads.add(thread)
      thread.start()

  def __len__(self):
    '''Returns the number of active threads plus the number of
    queued tasks/'''
    return len(self.threads) + len(self.tasks)

  @classmethod
  def instance(cls, name, thread_count=1, idle_timeout=60):
    '''A convenience method for accessing shared instances of ``TaskQueue``.
    If ``name`` references an existing instance created with this method,
    that instance will be returned. Otherwise, a new ``TaskQueue`` will be
    instantiated with ``thread_count`` threads and the specified ``idle_timeout``
    then stored under ``name``.

    All arguments after name are ignored after the queue is created.
    '''
    if not hasattr(cls, '_task_queues'):
      cls._task_queues = {}
    try:
      return cls._task_queues[name]
    except KeyError:
      cls._task_queues[name] = cls(thread_count, idle_timeout, name)
      return cls._task_queues[name]

  class __TaskLoop(Thread):

    thread_id = count()

    def __init__(self, queue):
      Thread.__init__(self, name='%s-%d' % (queue.name, self.thread_id.next()))
      self.daemon = True
      self.queue = queue
      self.condition = self.queue.condition
      self.tasks = self.queue.tasks
      self.idle_timeout = self.queue.idle_timeout
      self.threads = self.queue.threads
      self.in_use = True

    def run(self):
      try:
        while 1:
          with self.condition:
            if not len(self.tasks):
              self.condition.wait(self.idle_timeout)
            try:
              task = self.tasks.popleft()
            except IndexError:
              logging.debug('Idle timeout: %s' % self.name)
              self.threads.remove(self)
              self.in_use = False
              return
          try:
            task[0](*task[1], **task[2])
          except Exception as e:
            logging.error(traceback.format_exc())
      finally:
        with self.condition:
          if self.in_use:
            self.threads.remove(self)
            self.in_use = False

class InstancePool(object):
  ''' Create a pool wrapping one or more instances of a class. The pool has convenience methods for
  asynchronous execution and transactions. May be used e.g. to share non-threadsafe classes among
  various threads.

  Invoking a method other than those documented below will remove an instance from the pool, invoke
  the method, then return it to the pool.

  ``instances`` should be either a single instance or a collection of instances.

  ``default_queue`` is the name of the ``TaskQueue`` that will be used for all asynchronous operations.
  '''

  def __init__(self, instances, default_queue="pool"):
    pool = Queue()
    if hasattr(instances, '__iter__'):
      for i in instances:
        pool.put(i)
    else:
      pool.put(instances)
    self._pool = pool
    self._default_queue = default_queue

  def __getattr__(self, key):
    def call(*args, **kwargs):
      c = self._pool.get()
      try:
        return getattr(c, key)(*args, **kwargs)
      finally:
        self._pool.put(c)
    return call

  def await(self, queue_name=None):
    ''' Create an AwaitableInstance wrapping this queue.
    '''
    if not queue_name:
      queue_name = self._default_queue
    return AwaitableInstance(self, queue_name)

  def instance(self):
    ''' For use with the ``with`` operator. Allows multiple methods to be called on a single instance
    instance in the pool and returns it when complete.

    For example::

      with pool.instance() as i:
        i.operation1()
        i.operation2()

    Will remove an instance from the pool, call two methods on it, then return it to the queue.
    '''
    return self.__InstanceTransaction(self._pool)

  def transaction(self, function):
    ''' Calls ``function`` with an instance from the pool as the single argument. Returns the result
    of ``function(instance)``
    '''
    with self.instance() as i:
      return function(i)

  def async_transaction(self, function, queue_name=None):
    ''' Like ``transaction()`` but runs the operation in a ``TaskQueue``. ``queue_name`` may be specified
    to override the default.
    '''
    if not queue_name:
      queue_name = self._default_queue
    TaskQueue.instance(queue_name).add_task(self.transaction, function)

  def await_transaction(self, function, queue_name=None):
    ''' Like ``transaction()`` but runs the operation in a ``TaskQueue`` and returns a ``Future`` that
    may be used to retrieve the result. Must be called from a Tornado ``IOLoop``. ``queue_name`` may
    be specified to override the default.
    '''
    if not queue_name:
      queue_name = self._default_queue
    return TaskQueue.instance(queue_name).yield_task(self.transaction, function)

  def _get(self):
    return self._pool.get()

  def _put(self, i):
    return self._pool.put(i)

  class __InstanceTransaction(object):

    def __init__(self, pool):
      self._pool = pool

    def __enter__(self):
      self._instance = self._pool.get()
      return self._instance

    def __exit__(self, exc_type, exc_value, traceback):
      self._pool.put(self._instance)

class AwaitableInstance(object):
  ''' Use ``AwaitableInstance(instance)`` to create a wrapper around ``instance`` that may be used to
  automatically execute any of ``instance`` methods in a ``TaskQueue``. Use ``queue_name`` to specify
  the name of the ``TaskQueue`` to use.

  Usage::

    class MyClass(object):
      def do_something(self, arg):
        ...
        return result

    awaitable = AwaitableInstance(MyClass())
    result = yield awaitable.do_something(args)

  The above will call ``do_something()`` in a ``TaskQueue`` and await the result.
  '''

  def __init__(self, instance, queue_name="pool"):
    self.instance = instance
    self.task_queue = TaskQueue.instance(queue_name)

  def __getattr__(self, key):
    return lambda *args, **kwargs: self.task_queue.yield_task(getattr(self.instance, key), *args, **kwargs)
