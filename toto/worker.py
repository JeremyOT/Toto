'''The Toto worker and worker connection classes are designed to help build RPC systems,
allowing you to pass CPU intensive work to other processeses or machines. Workers
were originally designed for use with the Toto server, making it easy to perform
long running tasks without effecting the server's responsiveness, but they have been
designed to be used independently and have no direct ties to the web server
architecture.

``TotoWorkers`` and ``WorkerConnections`` use ZMQ for messaging and require the ``pyzmq`` module.

The ``TotoWorkerService`` has a built in message router that will round-robin balance incoming
messages. The router can be disabled through configuration if only one worker process is needed.
Alternatively, the router can be configured to run without any worker processes, allowing multiple
machines to share a common router.

Most of the time you'll only need this script to start your server::

  from toto.worker import TotoWorkerService
  
  TotoWorkerService('settings.conf').run()

Methods, startup functions and databases can all be configured with the conf file.

Run your startup script with --help to see all available options.
'''

import os
import zmq
from zmq.devices.basedevice import ProcessDevice
import tornado
from tornado.options import options
import logging
import zlib
import cPickle as pickle
import sys
import time
from threading import Thread
from multiprocessing import Process, cpu_count
from toto.service import TotoService, process_count, pid_path
from toto.dbconnection import configured_connection
from exceptions import *
from toto.options import safe_define

safe_define("method_module", default='methods', help="The root module to use for method lookup")
safe_define("remote_event_receivers", type=str, help="A comma separated list of remote event address that this event manager should connect to. e.g.: 'tcp://192.168.1.2:8889'", multiple=True)
safe_define("event_init_module", default=None, type=str, help="If defined, this module's 'invoke' function will be called with the EventManager instance after the main event handler is registered (e.g.: myevents.setup)")
safe_define("startup_function", default=None, type=str, help="An optional function to run on startup - e.g. module.function. The function will be called for each worker process after it is configured and before it starts listening for tasks with the named parameters worker and db_connection.")
safe_define("worker_bind_address", default="tcp://*:55555", help="The service will bind to this address with a zmq PULL socket and listen for incoming tasks. Tasks will be load balanced to all workers. If this is set to an empty string, workers will connect directly to worker_socket_address.")
safe_define("worker_socket_address", default="ipc:///tmp/workerservice.sock", help="The load balancer will use this address to coordinate tasks between local workers")
safe_define("control_socket_address", default="ipc:///tmp/workercontrol.sock", help="Workers will subscribe to messages on this socket and listen for control commands. If this is an empty string, the command option will have no effect")
safe_define("command", type=str, metavar='status|shutdown', help="Specify a command to send to running workers on the control socket")
safe_define("compression_module", type=str, help="The module to use for compressing and decompressing messages. The module must have 'decompress' and 'compress' methods. If not specified, no compression will be used. You can also set worker.compress and worker.decompress in your startup method for increased flexibility")
safe_define("serialization_module", type=str, help="The module to use for serializing and deserializing messages. The module must have 'dumps' and 'loads' methods. If not specified, cPickle will be used. You can also set worker.dumps and worker.loads in your startup method for increased flexibility")

class TotoWorkerService(TotoService):
  '''Instances can be configured in three ways:

  1. (Most common) Pass the path to a config file as the first parameter to the constructor.
  2. Pass config parameters as command line arguments to the initialization script.
  3. Pass keyword arguments to the constructor.

  Precidence is as follows:

  Keyword args, config file, command line
  '''
  def __init__(self, conf_file=None, **kwargs):
    module_options = {'method_module', 'event_init_module'}
    function_options = {'startup_function'}
    original_argv, sys.argv = sys.argv, [i for i in sys.argv if i.strip('-').split('=')[0] in module_options]
    self._load_options(conf_file, **{i: kwargs[i] for i in kwargs if i in module_options})
    modules = {getattr(options, i) for i in module_options if getattr(options, i)}
    for module in modules:
      __import__(module)
    function_modules = {getattr(options, i).rsplit('.', 1)[0] for i in function_options if getattr(options, i)}
    for module in function_modules:
      __import__(module)
    sys.argv = original_argv
    #clear root logger handlers to prevent duplicate logging if user has specified a log file
    super(TotoWorkerService, self).__init__(conf_file, **kwargs)
    #clear method_module references so we can fully reload with new options
    for module in modules:
      for i in (m for m in sys.modules.keys() if m.startswith(module)):
        del sys.modules[i]
    for module in function_modules:
      for i in (m for m in sys.modules.keys() if m.startswith(module)):
        del sys.modules[i]
    #prevent the reloaded module from re-defining options
    define, tornado.options.define = tornado.options.define, lambda *args, **kwargs: None
    self.__event_init = options.event_init_module and __import__(options.event_init_module) or None
    self.__method_module = options.method_module and __import__(options.method_module) or None
    tornado.options.define = define

  def prepare(self):
    self.balancer = None
    if options.worker_bind_address:
      self.balancer = ProcessDevice(zmq.QUEUE, zmq.ROUTER, zmq.DEALER)
      self.balancer.daemon = True
      self.balancer.bind_in(options.worker_bind_address)
      self.balancer.bind_out(options.worker_socket_address)
      self.balancer.setsockopt_in(zmq.IDENTITY, 'ROUTER')
      self.balancer.setsockopt_out(zmq.IDENTITY, 'DEALER')
      self.balancer.start()
      if options.daemon:
        with open(pid_path(0), 'wb') as f:
          f.write(str(self.balancer.launcher.pid))
    count = options.processes if options.processes >= 0 else cpu_count()
    if count == 0:
      print 'Starting load balancer. Listening on "%s". Routing to "%s"' % (options.worker_bind_address, options.worker_socket_address)
    else:
      print "Starting %s worker process%s. %s." % (count, count > 1 and 'es' or '', options.worker_bind_address and ('Listening on "%s"' % options.worker_bind_address) or ('Connecting to "%s"' % options.worker_socket_address))

  def main_loop(self):
    db_connection = configured_connection()

    if options.remote_event_receivers:
      from toto.events import EventManager
      event_manager = EventManager.instance()
      if options.remote_instances:
        for address in options.remote_event_receivers.split(','):
          event_manager.register_server(address)
      init_module = self.__event_init
      if init_module:
        init_module.invoke(event_manager)
    serialization = options.serialization_module and __import__(options.serialization_module) or pickle
    compression = options.compression_module and __import__(options.compression_module)
    worker = TotoWorker(self.__method_module, options.worker_socket_address, db_connection, compression, serialization)
    if options.startup_function:
      startup_path = options.startup_function.rsplit('.')
      __import__(startup_path[0]).__dict__[startup_path[1]](worker=worker, db_connection=db_connection)
    worker.start()

  def send_worker_command(self, command):
    if options.control_socket_address:
      socket = zmq.Context().socket(zmq.PUB)
      socket.bind(options.control_socket_address)
      time.sleep(1)
      socket.send_string('command %s' % command)
      print "Sent command: %s" % options.command

  def run(self): 
    if options.command:
      self.send_worker_command(options.command)
      return
    super(TotoWorkerService, self).run()

class TotoWorker():
  '''The worker is responsible for processing all RPC calls. An instance
  will be initialized for each incoming request.
  
  You can set the module to use for method delegation via the ``method_module`` parameter.
  Methods are modules that contain an invoke function::

    def invoke(handler, parameters)
  
  The request worker instance will be passed as the first parameter to the invoke function and
  provides access to the server's database connection. Request parameters will be passed as the
  second argument to the invoke function.

  Any value returned from a method invocation will be sent to the caller, closing the
  message->response cycle. If you only need to let the caller know that the task has begun, you
  should decorate your ``invoke`` function with ``@toto.invocation.asynchronous`` to send a
  response before processing begins.
  '''
  def __init__(self, method_module, socket_address, db_connection, compression=None, serialization=None):
    self.context = zmq.Context()
    self.socket_address = socket_address
    self.method_module = method_module
    self.db_connection = db_connection
    self.db = db_connection and db_connection.db or None
    self.status = 'Initialized'
    self.running = False
    self.compress = compression and compression.compress or (lambda x: x)
    self.decompress = compression and compression.decompress or (lambda x: x)
    self.loads = serialization and serialization.loads or pickle.loads
    self.dumps = serialization and serialization.dumps or pickle.dumps
    if options.debug:
      from traceback import format_exc
      def error_info(self, e):
        if not isinstance(e, TotoException):
          e = TotoException(ERROR_SERVER, str(e))
        logging.error('%s\n%s\n' % (e, format_exc()))
        return e.__dict__
      TotoWorker.error_info = error_info
  
  def error_info(self, e):
    if not isinstance(e, TotoException):
      e = TotoException(ERROR_SERVER, str(e))
    logging.error(str(e))
    return e.__dict__

  def log_status(self):
    logging.info('Pid: %s status: %s' % (os.getpid(), self.status))
  
  def __monitor_control(self, address=options.control_socket_address):
    def monitor():
      socket = self.context.socket(zmq.SUB)
      socket.setsockopt(zmq.SUBSCRIBE, 'command')
      socket.connect(address)
      while self.running:
        try:
          command = socket.recv().split(' ', 1)[1]
          logging.info("Received command: %s" % command)
          if command == 'shutdown':
            self.running = False
            self.context.term()
            return
          elif command == 'status':
            self.log_status()
        except Exception as e:
          self.error_info(e)
    if address:
      thread = Thread(target=monitor)
      thread.daemon = True
      thread.start()

  def start(self):
    self.running = True
    self.__monitor_control()
    socket = self.context.socket(zmq.REP)
    socket.connect(self.socket_address)
    pending_reply = False
    while self.running:
      try:
        self.status = 'Listening'
        message = socket.recv_multipart()
        pending_reply = True
        message_id = message[0]
        data = self.loads(self.decompress(message[1]))
        logging.info('Received Task %s: %s' % (message_id, data['method']))
        method = self.method_module
        for i in data['method'].split('.'):
          method = getattr(method, i)
        if hasattr(method.invoke, 'asynchronous'):
          socket.send_multipart((message_id,))
          pending_reply = False
          self.status = 'Working'
          method.invoke(self, data['parameters'])
        else:
          self.status = 'Working'
          response = method.invoke(self, data['parameters'])
          socket.send_multipart((message_id, self.compress(self.dumps(response))))
          pending_reply = False
      except Exception as e:
        if pending_reply:
          socket.send_multipart((message_id, self.compress(self.dumps({'error': self.error_info(e)}))))

    self.status = 'Finished'
    self.log_status()
