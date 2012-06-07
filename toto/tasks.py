from threading import Thread, Lock
from collections import deque
import logging
import traceback

_task_queues = {}

class TaskQueue():

  def __init__(self, thread_count=1):
    self.tasks = deque()
    self.running = False
    self.lock = Lock()
    self.threads = set()
    self.thread_count = thread_count
  
  def add_task(self, fn, args=[]):
    self.tasks.append((fn, args))
    self.lock.acquire()
    self.run()
    self.lock.release()

  def run(self):
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
        task[0](*task[1])
    thread = Thread(target=task_loop)
    thread.daemon = True
    self.threads.add(thread)
    thread.start()

  def __len__(self):
    return len(self.threads) + len(self.tasks)

  @staticmethod
  def instance(name, thread_count=1):
    try:
      return _task_queues[name]
    except KeyError:
      _task_queues[name] = TaskQueue(thread_count)
      return _task_queues[name]
