from threading import Thread, Lock
from collections import deque

_task_queues = {}

class TaskQueue():

  def __init__(self):
    self.tasks = deque()
    self.running = False
    self.lock = Lock()
  
  def add_task(self, fn, args=[]):
    self.tasks.append((fn, args))
    self.lock.acquire()
    if not self.running:
      self.run()
    self.lock.release()

  def run(self):
    if self.running:
      return
    self.running = True
    def task_loop():
      while 1:
        self.lock.acquire()
        try:
          task = self.tasks.popleft()
        except IndexError:
          self.running = False
          return
        finally:
          self.lock.release()
        task[0](*task[1])
    Thread(target=task_loop).start()

  @staticmethod
  def instance(name):
    try:
      return _task_queues[name]
    except KeyError:
      _task_queues[name] = TaskQueue()
      return _task_queues[name]
