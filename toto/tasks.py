'''Toto provides build a built in task queue for performing work in the background
while limiting the number of active jobs. The task queue is designed primarily for
shorter, lightweight jobs. For CPU intensive tasks or tasks that are expected to
run for a long time, look at Toto's worker functionality instead.
'''
from threading import Thread, Lock
from collections import deque
from tornado.gen import coroutine, Task, Return
import logging
import traceback

class TaskQueue():
  '''Instances will run up to ``thread_count`` tasks at a time
  whenever there are tasks in the queue.
  '''

  def __init__(self, thread_count=1):
    self.tasks = deque()
    self.running = False
    self.lock = Lock()
    self.threads = set()
    self.thread_count = thread_count
  
  def add_task(self, fn, *args, **kwargs):
    '''Add the function ``fn`` to the queue to be invoked with
    ``args`` and ``kwargs`` as arguments. If the ``TaskQueue``
    is not currently running, it will be started now.
    '''
    self.tasks.append((fn, args, kwargs))
    self.lock.acquire()
    self.run()
    self.lock.release()

  @coroutine
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
    def call(callback):
      result = None
      error = None
      try:
        result = fn(*args, **kwargs)
      except Exception as e:
        error = e
      callback(result, error)
    (result, error), _ = yield Task(lambda callback: self.add_task(call, callback))
    if error:
      raise error
    raise Return(result)

  def run(self):
    '''Start processing jobs in the queue. You should not need
    to call this as ``add_task`` automatically starts the queue.
    Processing threads will stop when there are no jobs available
    in the queue.
    '''
    if len(self.threads) >= self.thread_count:
      return
    thread = None
    def task_loop():
      while 1:
        self.lock.acquire()
        try:
          task = self.tasks.popleft()
        except IndexError:
          self.threads.remove(thread)
          return
        except Exception as e:
          logging.error(traceback.format_exc())
        finally:
          self.lock.release()
        task[0](*task[1], **task[2])
    thread = Thread(target=task_loop)
    thread.daemon = True
    self.threads.add(thread)
    thread.start()

  def __len__(self):
    '''Returns the number of active threads plus the number of
    queued tasks/'''
    return len(self.threads) + len(self.tasks)

  @classmethod
  def instance(cls, name, thread_count=1):
    '''A convenience method for accessing shared instances of ``TaskQueue``.
    If ``name`` references an existing instance created with this method,
    that instance will be returned. Otherwise, a new ``TaskQueue`` will be
    instantiated with ``thread_count`` threads and stored under ``name``.
    '''
    if not hasattr(cls, '_task_queues'):
      cls._task_queues = {}
    try:
      return cls._task_queues[name]
    except KeyError:
      cls._task_queues[name] = cls(thread_count)
      return cls._task_queues[name]
