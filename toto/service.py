'''``TotoService`` can be used to write general processes that take advantage of the process creation/management features
  used by ``TotoServer`` and ``TotoWorker`` - the two built in subclasses of ``TotoService``.  ``TotoService`` subclasses can be
  run with the ``--start`` (or ``--stop``)  and ``--processes`` options
  to start the service as a daemon process or run multiple instances simultaneously.
  
  To run a subclass of ``TotoService`` create a script like this::

    from toto.service import TotoService

    class MyServiceSubclass(TotoService):

      def main_loop(self):
        while 1:
          #run some job continuously

    MyServiceSubclass('conf_file.conf').run()
'''

import os
import tornado
import logging
from tornado.options import define, options
from multiprocessing import Process, cpu_count
from time import sleep

define("daemon", metavar='start|stop|restart', help="Start, stop or restart this script as a daemon process. Use this setting in conf files, the shorter start, stop, restart aliases as command line arguments. Requires the multiprocessing module.")
define("processes", default=1, help="The number of daemon processes to run")
define("pidfile", default="toto.daemon.pid", help="The path to the pidfile for daemon processes will be named <path>.<num>.pid (toto.daemon.pid -> toto.daemon.0.pid)")
define("start", default=False, help="Alias for daemon=start for command line usage - overrides daemon setting.")
define("stop", default=False, help="Alias for daemon=start for command line usage - overrides daemon setting.")
define("restart", default=False, help="Alias for daemon=start for command line usage - overrides daemon setting.")
define("nodaemon", default=False, help="Alias for daemon='' for command line usage - overrides daemon setting.")
define("debug", default=False, help="Set this to true to prevent Toto from nicely formatting generic errors. With debug=True, errors will print to the command line")

#convert p to the absolute path, insert ".i" before the last "." or at the end of the path
def pid_path(i):
  '''Used to generate PID files for daemonized TotoServices. Child processes with PID files
  matching the paths returned by this function will be killed with SIGTERM when the server daemon process is stopped using the
  ``--stop`` or ``--daemon=stop`` arguments::

    proc = Process()
    proc.start()
    with open(pid_path(process_count() + 1), 'wb') as f:
      f.write(str(proc.pid))
  
  Note that ``i`` must be an integer.
  '''
  (d, f) = os.path.split(os.path.abspath(options.pidfile))
  components = f.rsplit('.', 1)
  f = '%s.%s' % (components[0], i)
  if len(components) > 1:
    f += "." + components[1]
  return os.path.join(d, f)

def process_count():
  '''Returns the number of service processes that will run with the current configuration. This will match
  the ``--processes=n`` option if n >= 0. Otherwise ``multiprocessing.cpu_count()`` will be used.
  '''
  return options.processes if options.processes >= 0 else cpu_count()


class TotoService(object):
  '''Subclass ``TotoService`` to create a service that can be easily daemonised or
  ran in multiple processes simultaneously.
  '''

  def _load_options(self, conf_file=None, final=True, **kwargs):
    for k in kwargs:
      setattr(options, k, kwargs[k])
    if conf_file:
      tornado.options.parse_config_file(conf_file, final=False)
    tornado.options.parse_command_line(final=final)
    if options.start:
      setattr(options, 'daemon', 'start')
    elif options.stop:
      setattr(options, 'daemon', 'stop')
    elif options.restart:
      setattr(options, 'daemon', 'restart')
    elif options.nodaemon:
      setattr(options, 'daemon', '')

  def __init__(self, conf_file=None, **kwargs):
    if options.log_file_prefix:
      root_logger = logging.getLogger()
      for handler in [h for h in root_logger.handlers]:
        root_logger.removeHandler(handler)
    self._load_options(conf_file, **kwargs)

  def __run_service(self, pidfile=None):

    def start_server_process(pidfile, service_id=0):
      self.service_id = service_id
      self.main_loop()
      if pidfile:
        os.remove(pidfile)
    count = process_count()
    processes = []
    pidfiles = options.daemon and [pid_path(i) for i in xrange(1, count + 1)] or []
    self.prepare()
    for i in xrange(count):
      proc = Process(target=start_server_process, args=(pidfiles and pidfiles[i], i))
      proc.daemon = True
      processes.append(proc)
      proc.start()
    else:
      print "Starting %s %s process%s." % (count, self.__class__.__name__, count > 1 and 'es' or '')
    if options.daemon:
      i = 1
      for proc in processes:
        with open(pidfiles[i - 1], 'w') as f:
          f.write(str(proc.pid))
        i += 1
    for proc in processes:
      proc.join()
    self.finish()
    if pidfile:
      os.remove(pidfile)

  def run(self): 
    '''Start the service. Depending on the initialization options, this may run more than one
    service process.
    '''
    if options.daemon:
      import multiprocessing
      import signal, re

      pattern = pid_path(r'\d+').replace('.', r'\.')
      piddir = os.path.dirname(pattern).replace('\\.', '.')
      master_pidfile = pid_path('master')

      if options.daemon == 'stop' or options.daemon == 'restart':
        existing_pidfiles = [pidfile for pidfile in (os.path.join(piddir, fn) for fn in os.listdir(piddir)) if re.match(pattern, pidfile)]
        try:
          with open(master_pidfile, 'rb') as f:
            master_pid = int(f.read())
        except:
          master_pid = 0
        for pidfile in existing_pidfiles:
          try:
            with open(pidfile, 'r') as f:
              pid = int(f.read())
            try:
              os.kill(pid, signal.SIGTERM)
            except OSError as e:
              if e.errno != 3:
                raise
            print "Stopped %s %s" % (self.__class__.__name__, pid)
            os.remove(pidfile)
          except (OSError, IOError) as e:
            if e.errno != 2:
              raise
        if not existing_pidfiles and master_pid:
          try:
            os.kill(master_pid, signal.SIGTERM)
          except OSError as e:
            if e.errno != 3:
              raise
          os.remove(master_pidfile)
          print 'Force stopped %s %s' % (self.__class__.__name__, master_pid)
        else:
          while os.path.exists(master_pidfile):
            sleep(0.01)

      if options.daemon == 'start' or options.daemon == 'restart':
        existing_pidfiles = [pidfile for pidfile in (os.path.join(piddir, fn) for fn in os.listdir(piddir)) if re.match(pattern.replace(r'\d', r'[\w\d]'), pidfile)]
        if existing_pidfiles:
          print "Not starting %s, pidfile%s exist%s at %s" % (self.__class__.__name__, len(existing_pidfiles) > 1 and 's' or '', len(existing_pidfiles) == 1 and 's' or '', ', '.join(existing_pidfiles))
          return
        #fork and only continue on child process
        if not os.fork():
          #detach from controlling terminal
          os.setsid()
          #fork again and write pid to pidfile from parent, run server on child
          pid = os.fork()
          if pid:
            with open(master_pidfile, 'w') as f:
              f.write(str(pid))
          else:
            self.__run_service(master_pidfile)

      if options.daemon not in ('start', 'stop', 'restart'):
        print "Invalid daemon option: " + options.daemon

    else:
      self.__run_service()

  def prepare(self):
    '''Override this method in a ``TotoService`` subclass and it will be called before any service processes
    are created. You can set instance variables here and they will be available in ``main_loop()`` but be
    careful that any retained objects are safe to access across processes'''
    pass

  def main_loop(self):
    '''Subclass ``TotoService`` and override ``main_loop()`` with your desired functionality.'''
    raise NotImplementedError()

  def finish(self):
    '''Override this method in a ``TotoService`` subclass and it will be called after all service processes
    have exited (after each ``main_loop()`` has returned).

    Note: This method will only be called once and only after all child processes have finished.'''
    pass

