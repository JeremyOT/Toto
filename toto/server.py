import os
from tornado.web import *
from tornado.ioloop import *
from tornado.options import define, options
from handler import TotoHandler
from sockets import TotoSocketHandler
from remoteworker import RemoteWorkerSocketHandler
import logging

define("database", metavar='mysql|mongodb|none', default="mongodb", help="the database driver to use (default 'mongodb')")
define("mysql_host", default="localhost:3306", help="MySQL database 'host:port' (default 'localhost:3306')")
define("mysql_database", type=str, help="Main MySQL schema name")
define("mysql_user", type=str, help="Main MySQL user")
define("mysql_password", type=str, help="Main MySQL user password")
define("mongodb_host", default="localhost", help="MongoDB host (default 'localhost')")
define("mongodb_port", default=27017, help="MongoDB port (default 27017)")
define("mongodb_database", default="toto_server", help="MongoDB database (default 'toto_server')")
define("port", default=8888, help="The port to run this server on. Multiple daemon servers will be numbered sequentially starting at this port. (default 8888)")
define("daemon", metavar='start|stop|restart', help="Start, stop or restart this script as a daemon process. Use this setting in conf files, the shorter start, stop, restart aliases as command line arguments. Requires the multiprocessing module.")
define("processes", default=1, help="The number of daemon processes to run, pass 0 to run one per cpu (default 1)")
define("pidfile", default="toto.pid", help="The path to the pidfile for daemon processes will be named <path>.<num>.pid (default toto.pid -> toto.0.pid)")
define("root", default='/', help="The path to run the server on. This can be helpful when hosting multiple services on the same domain (default /)")
define("method_module", default='methods', help="The root module to use for method lookup (default method)")
define("remote_instances", type=str, help="A comma separated list of remote event address that this event manager should connect to. e.g.: 'tcp://192.168.1.2:8889'")
define("session_ttl", default=24*60*60*365, help="The number of seconds after creation a session should expire (default 1 year)")
define("anon_session_ttl", default=24*60*60, help="The number of seconds after creation an anonymous session should expire (default 1 day)")
define("session_renew", default=0, help="The number of seconds before a session expires that it should be renewed, or zero to renew on every request (default 0)")
define("anon_session_renew", default=0, help="The number of seconds before an anonymous session expires that it should be renewed, or zero to renew on every request (default 0)")
define("password_salt", default='toto', help="An additional salt to use when generating a password hash - changing this value will invalidate all stored passwords (default toto)")
define("cookie_secret", default=None, type=str, help="A long random string to use as the HMAC secret for secure cookies, ignored if use_cookies is not enabled")
define("autoreload", default=False, help="This option autoreloads modules as changes occur - useful for debugging.")
define("event_mode", default='off', metavar='off|on|only', help="This option enables or disables the event system, also providing an option to launch this server as an event server only")
define("event_init_module", default=None, type=str, help="If defined, this module's 'invoke' function will be called with the EventManager instance after the main event handler is registered (e.g.: myevents.setup)")
define("start", default=False, help="Alias for daemon=start for command line usage - overrides daemon setting.")
define("stop", default=False, help="Alias for daemon=start for command line usage - overrides daemon setting.")
define("restart", default=False, help="Alias for daemon=start for command line usage - overrides daemon setting.")
define("nodaemon", default=False, help="Alias for daemon='' for command line usage - overrides daemon setting.")
define("startup_function", default=None, type=str, help="An optional function to run on startup - e.g. module.function. The function will be called for each server instance before the server start listening as function(connection=<active database connection>, application=<tornado.web.Application>).")
define("debug", default=False, help="Set this to true to prevent Toto from nicely formatting generic errors. With debug=True, errors will print to the command line")
define("use_cookies", default=False, help="Select whether to use cookies for session storage, replacing the x-toto-session-id header. You must set cookie_secret if using this option and secure_cookies is not set to False (default False)")
define("secure_cookies", default=True, help="If using cookies, select whether or not they should be secure. Secure cookies require cookie_secret to be set (default True)")
define("cookie_domain", default=None, type=str, help="The value to use for the session cookie's domain attribute - e.g. '.example.com' (default None)")
define("socket_opened_method", default=None, type=str, help="An optional function to run when a new web socket is opened, the socket handler will be passed as the only argument")
define("socket_closed_method", default=None, type=str, help="An optional function to run when a web socket is closed, the socket handler will be passed as the only argument")
define("socket_method_module", default=None, type=str, help="The root module to use for web socket method lookup")
define("use_web_sockets", default=False, help="Whether or not web sockets should be installed as an alternative way to call methods (default False)")
define("socket_path", default='websocket', help="The path to use for websocket connections (default 'websocket')")
define("use_remote_workers", default=False, help="Whether or not to use Toto's remote worker functionality (default False)")
define("remote_worker_path", default="remoteworker", help="The path to use for remote worker connections (default 'remoteworker')")
define("event_port", default=8999, help="The address to listen to event connections on - due to message queuing, servers use the next higher port as well (default '8999')")

class TotoServer():

  def __load_options(self, conf_file=None, **kwargs):
    for k in kwargs:
      options[k].set(kwargs[k])
    if conf_file:
      tornado.options.parse_config_file(conf_file)
    tornado.options.parse_command_line()
    if options.start:
      options['daemon'].set('start')
    elif options.stop:
      options['daemon'].set('stop')
    elif options.restart:
      options['daemon'].set('restart')
    elif options.nodaemon:
      options['daemon'].set('')
    

  def __init__(self, conf_file=None, **kwargs):
    module_options = {'method_module', 'socket_method_module', 'event_init_module'}
    function_options = {'startup_function', 'socket_opened_method', 'socket_closed_method'}
    original_argv, sys.argv = sys.argv, [i for i in sys.argv if i.strip('-').split('=')[0] in module_options]
    self.__load_options(conf_file, **{i: kwargs[i] for i in kwargs if i in module_options})
    modules = {getattr(options, i) for i in module_options if getattr(options, i)}
    for module in modules:
      __import__(module)
    function_modules = {getattr(options, i).rsplit('.', 1)[0] for i in function_options if getattr(options, i)}
    for module in function_modules:
      __import__(module)
    sys.argv = original_argv
    #clear root logger handlers to prevent duplicate logging if user has specified a log file
    if options.log_file_prefix:
      root_logger = logging.getLogger()
      for handler in [h for h in root_logger.handlers]:
        root_logger.removeHandler(handler)
    self.__load_options(conf_file, **kwargs)
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
    TotoHandler.configure()
    if options.use_web_sockets:
      TotoSocketHandler.configure()
    if options.use_remote_workers:
      RemoteWorkerSocketHandler.configure()
    tornado.options.define = define

  def __run_server(self, port, index=0):
    db_connection = None
    if options.database == "mongodb":
      from mongodbconnection import MongoDBConnection
      db_connection = MongoDBConnection(options.mongodb_host, options.mongodb_port, options.mongodb_database, options.password_salt, options.session_ttl, options.anon_session_ttl, options.session_renew, options.anon_session_renew)
    elif options.database == "mysql":
      from mysqldbconnection import MySQLdbConnection
      db_connection = MySQLdbConnection(options.mysql_host, options.mysql_database, options.mysql_user, options.mysql_password, options.password_salt, options.session_ttl, options.anon_session_ttl, options.session_renew, options.anon_session_renew)
    else:
      from fakeconnection import FakeConnection
      db_connection = FakeConnection()
  
    application_settings = {}
    if options.cookie_secret:
      application_settings['cookie_secret'] = options.cookie_secret
    if options.autoreload:
      application_settings['debug'] = True

    handlers = []
    if options.use_web_sockets:
      handlers.append(('%s/?([^/]?[\w\./]*)' % os.path.join(options.root, options.socket_path), TotoSocketHandler, {'db_connection': db_connection}))
    if options.use_remote_workers:
      handlers.append((os.path.join(options.root, options.remote_worker_path), RemoteWorkerSocketHandler))
    if not options.event_mode == 'off':
      from toto.events import EventManager
      event_manager = EventManager.instance()
      event_manager.address = 'tcp://*:%s' % (options.event_port + index)
      event_manager.start_listening()
      for i in xrange(options.processes > 0 and options.processes or multiprocessing.cpu_count()):
        event_manager.register_server('tcp://127.0.0.1:%s' % (options.event_port + i))
      if options.remote_instances:
        for address in options.remote_instances.split(','):
          event_manager.register_server(address)
      init_module = self.__event_init
      if init_module:
        init_module.invoke(event_manager)
    if not options.event_mode == 'only':
      handlers.append(('%s/?([^/]?[\w\./]*)' % options.root.rstrip('/'), TotoHandler, {'db_connection': db_connection}))
    
    application = Application(handlers, **application_settings)
    
    if options.startup_function:
      startup_path = options.startup_function.rsplit('.')
      __import__(startup_path[0]).__dict__[startup_path[1]](db_connection=db_connection, application=application)

    application.listen(port)
    print "Starting server on port %s" % port
    IOLoop.instance().start()

  def run(self): 
    if options.daemon:
      import multiprocessing
      #convert p to the absolute path, insert ".i" before the last "." or at the end of the path
      def path_with_id(p, i):
        (d, f) = os.path.split(os.path.abspath(p))
        components = f.rsplit('.', 1)
        f = '%s.%s' % (components[0], i)
        if len(components) > 1:
          f += "." + components[1]
        return os.path.join(d, f)

      count = options.processes > 0 and options.processes or multiprocessing.cpu_count()
      if options.daemon == 'stop' or options.daemon == 'restart':
        import signal, re
        pattern = path_with_id(options.pidfile, r'\d+').replace('.', r'\.')
        piddir = os.path.dirname(pattern)
        for fn in os.listdir(os.path.dirname(pattern)):
          pidfile = os.path.join(piddir, fn)
          if re.match(pattern, pidfile):
            with open(pidfile, 'r') as f:
              pid = int(f.read())
              try:
                os.kill(pid, signal.SIGTERM)
              except OSError as e:
                if e.errno != 3:
                  raise
              print "Stopped server %s" % pid 
            os.remove(pidfile)

      if options.daemon == 'start' or options.daemon == 'restart':
        import sys
        def run_daemon_server(port, pidfile, index):
          #fork and only continue on child process
          if not os.fork():
            #detach from controlling terminal
            os.setsid()
            #fork again and write pid to pidfile from parent, run server on child
            pid = os.fork()
            if pid:
              with open(pidfile, 'w') as f:
                f.write(str(pid))
            else:
              self.__run_server(port, index)

        for i in xrange(count):
          pidfile = path_with_id(options.pidfile, i)
          if os.path.exists(pidfile):
            print "Skipping %d, pidfile exists at %s" % (i, pidfile)
            continue

          p = multiprocessing.Process(target=run_daemon_server, args=(options.port + i, pidfile, i))
          p.start()
      if options.daemon not in ('start', 'stop', 'restart'):
        print "Invalid daemon option: " + options.daemon

    else:
      self.__run_server(options.port)
