import events
import os
from tornado.web import *
from tornado.ioloop import *
from tornado.options import define, options
from handler import *
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
define("event_key", type=str, help="The string to use for the x-toto-event-key header when sending events to the event manager. By default this is auto generated on launch, but a value can be passed to facilitate sending events from external processes")
define("remote_instances", type=str, help="A comma separated list of remote servers (http://192.168.1.2:8888/) or event handlers (!http://192.168.1.2:9000/handler_path) that should be treated as instances of this server. Set this parameter to have the event system send events to remote servers (event_key is required to match on all servers in this list).")
define("session_ttl", default=24*60*60*365, help="The number of seconds after creation a session should expire (default 1 year)")
define("anon_session_ttl", default=24*60*60, help="The number of seconds after creation an anonymous session should expire (default 1 day)")
define("session_renew", default=0, help="The number of seconds before a session expires that it should be renewed, or zero to renew on every request (default 0)")
define("anon_session_renew", default=0, help="The number of seconds before an anonymous session expires that it should be renewed, or zero to renew on every request (default 0)")
define("password_salt", default='toto', help="An additional salt to use when generating a password hash - changing this value will invalidate all stored passwords (default toto)")
define("cookie_secret", default=None, type=str, help="A long random string to use as the HMAC secret for secure cookies, ignored if use_cookies is not enabled")
define("autoreload", default=False, help="This option autoreloads modules as changes occur - useful for debugging.")
define("event_path", default='event', help="The path to listen for events on - primarily used for internal communication (default event)")
define("event_mode", default='off', metavar='off|on|only', help="This option enables or disables the event system, also providing an option to launch this server as an event server only")
define("event_init_module", default=None, type=str, help="If defined, this module's 'invoke' function will be called with the EventManager instance after the main event handler is registered (e.g.: myevents.setup)")
define("start", default=False, help="Alias for daemon=start for command line usage - overrides daemon setting.")
define("stop", default=False, help="Alias for daemon=start for command line usage - overrides daemon setting.")
define("restart", default=False, help="Alias for daemon=start for command line usage - overrides daemon setting.")
define("nodaemon", default=False, help="Alias for daemon='' for command line usage - overrides daemon setting.")
define("startup_function", default=None, type=str, help="An optional function to run on startup - e.g. module.function. The function will be called for each server instance before the server start listening as function(connection=<active database connection>, application=<tornado.web.Application>).")

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
    original_argv, sys.argv = sys.argv, [i for i in sys.argv if i.startswith('--method_module=')]
    self.__load_options(conf_file, **('method_module' in kwargs and {'method_module': kwargs['method_module']} or {}))
    self.__method = options.method_module and __import__(options.method_module) or None
    self.__event_init = options.event_init_module and __import__(options.event_init_module) or None
    sys.argv = original_argv
    #clear root logger handlers to prevent duplicate logging if user has specified a log file
    if options.log_file_prefix:
      root_logger = logging.getLogger()
      for handler in [h for h in root_logger.handlers]:
        root_logger.removeHandler(handler)
    self.__load_options(conf_file, **kwargs)
    #clear method_module references so we can fully reload with new options
    if self.__method:
      for i in (m for m in sys.modules.keys() if m.startswith(options.method_module)):
        del sys.modules[i]
    if self.__event_init:
      for i in (m for m in sys.modules.keys() if m.startswith(options.event_init_module)):
        del sys.modules[i]
    #prevent the reloaded module from re-defining options
    define, tornado.options.define = tornado.options.define, lambda *args, **kwargs: None
    self.__method = options.method_module and __import__(options.method_module) or None
    self.__event_init = options.event_init_module and __import__(options.event_init_module) or None
    tornado.options.define = define
    TotoHandler.configure()

  def __run_server(self, port):
    connection = None
    if options.database == "mongodb":
      from mongodbconnection import MongoDBConnection
      connection = MongoDBConnection(options.mongodb_host, options.mongodb_port, options.mongodb_database, options.password_salt, options.session_ttl, options.anon_session_ttl, options.session_renew, options.anon_session_renew)
    elif options.database == "mysql":
      from mysqldbconnection import MySQLdbConnection
      connection = MySQLdbConnection(options.mysql_host, options.mysql_database, options.mysql_user, options.mysql_password, options.password_salt, options.session_ttl, options.anon_session_ttl, options.session_renew, options.anon_session_renew)
    else:
      from fakeconnection import FakeConnection
      connection = FakeConnection()
  
    application_settings = {}
    if options.cookie_secret:
      application_settings['cookie_secret'] = options.cookie_secret
    if options.autoreload:
      application_settings['debug'] = True

    event_handler = (os.path.join(options.root, options.event_path), events.EventHandler)
    main_handler = ('%s/?([^/]?[\w\./]*)' % options.root.rstrip('/'), TotoHandler, {'method_root': self.__method, 'connection': connection})
    handlers = []
    if not options.event_mode == 'off':
      handlers.append(event_handler)
      init_module = self.__event_init
      if init_module:
        init_module.invoke(EventManager.instance())
    if not options.event_mode == 'only':
      handlers.append(main_handler)
    
    application = Application(handlers, **application_settings)
    
    if options.startup_function:
      startup_path = options.startup_function.rpartition('.')
      __import__(startup_path[0]).__dict__[startup_path[2]](connection=connection, application=application)

    application.listen(port)
    print "Starting server on port %s" % port
    IOLoop.instance().start()

  def run(self): 
    events.set_key(options.event_key)
    if options.remote_instances:
      for route in options.remote_instances.split(','):
        events.add_route(route[0] == '!' and route[1:] or os.path.join(route, options.event_path))
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
        def run_daemon_server(port, pidfile):
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
              self.__run_server(port)

        for i in xrange(count):
          events.add_route(os.path.join("http://127.0.0.1:%d%s" % (options.port + i, options.root), options.event_path))

        for i in xrange(count):
          pidfile = path_with_id(options.pidfile, i)
          if os.path.exists(pidfile):
            print "Skipping %d, pidfile exists at %s" % (i, pidfile)
            continue

          events.set_local_route(os.path.join("http://127.0.0.1:%d%s" % (options.port + i, options.root), options.event_path))
          p = multiprocessing.Process(target=run_daemon_server, args=(options.port + i, pidfile))
          p.start()
      if options.daemon not in ('start', 'stop', 'restart'):
        print "Invalid daemon option: " + options.daemon

    else:
      event_route = os.path.join("http://127.0.0.1:%d%s" % (options.port, options.root), options.event_path)
      events.add_route(event_route)
      events.set_local_route(event_route)
      self.__run_server(options.port)
