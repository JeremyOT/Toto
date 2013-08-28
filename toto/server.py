'''The Toto server and handler classes are designed to simplify most of the boilerplate that comes with
building web services so you can focus on the important parts specific to your application.

Most of the time you'll only need this script to start your server::

  from toto.server import TotoServer
  
  TotoServer('settings.conf').run()

Methods, startup functions and databases can all be configured with the conf file.

Run your startup script with --help to see all available options.
'''

import os
import sys
import logging
import tornado
from tornado.web import Application
from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPServer
from tornado.options import options
from tornado.netutil import bind_sockets
from handler import TotoHandler
from toto.service import TotoService, process_count
from dbconnection import configured_connection
from toto.options import safe_define

safe_define("port", default=8888, help="The port this server will bind to.")
safe_define("root", default='/', help="The path to run the server on. This can be helpful when hosting multiple services on the same domain")
safe_define("method_module", default='methods', help="The root module to use for method lookup")
safe_define("cookie_secret", default=None, type=str, help="A long random string to use as the HMAC secret for secure cookies, ignored if use_cookies is not enabled")
safe_define("autoreload", default=False, help="This option autoreloads modules as changes occur - useful for debugging.")
safe_define("remote_event_receivers", type=str, help="A comma separated list of remote event address that this event manager should connect to. e.g.: 'tcp://192.168.1.2:8889'", multiple=True)
safe_define("event_mode", default='off', metavar='off|on|only', help="This option enables or disables the event system, also providing an option to launch this server as an event server only")
safe_define("event_init_module", default=None, type=str, help="If defined, this module's 'invoke' function will be called with the EventManager instance after the main event handler is registered (e.g.: myevents.setup)")
safe_define("event_port", default=8999, help="The address to listen to event connections on - due to message queuing, servers use the next higher port as well")
safe_define("startup_function", default=None, type=str, help="An optional function to run on startup - e.g. module.function. The function will be called for each server instance before the server starts listening as function(connection=<active database connection>, application=<tornado.web.Application>).")
safe_define("use_cookies", default=False, help="Select whether to use cookies for session storage, replacing the x-toto-session-id header. You must set cookie_secret if using this option and secure_cookies is not set to False")
safe_define("secure_cookies", default=True, help="If using cookies, select whether or not they should be secure. Secure cookies require cookie_secret to be set")
safe_define("cookie_domain", default=None, type=str, help="The value to use for the session cookie's domain attribute - e.g. '.example.com'")
safe_define("socket_opened_method", default=None, type=str, help="An optional function to run when a new web socket is opened, the socket handler will be passed as the only argument")
safe_define("socket_closed_method", default=None, type=str, help="An optional function to run when a web socket is closed, the socket handler will be passed as the only argument")
safe_define("socket_method_module", default=None, type=str, help="The root module to use for web socket method lookup")
safe_define("use_web_sockets", default=False, help="Whether or not web sockets should be installed as an alternative way to call methods")
safe_define("socket_path", default='websocket', help="The path to use for websocket connections")
safe_define("client_side_worker_path", default="", help="The path to use for client side worker connections - functionality will be disabled if this is not set.")

class TotoServer(TotoService):
  '''Instances can be configured in three ways:

  1. (Most common) Pass the path to a config file as the first parameter to the constructor.
  2. Pass config parameters as command line arguments to the initialization script.
  3. Pass keyword arguments to the constructor.

  Precidence is as follows:

  Keyword args, config file, command line
  '''

  def __init__(self, conf_file=None, **kwargs):
    module_options = {'method_module', 'socket_method_module', 'event_init_module'}
    function_options = {'startup_function', 'socket_opened_method', 'socket_closed_method'}
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
    super(TotoServer, self).__init__(conf_file, **kwargs)
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
      from sockets import TotoSocketHandler
      TotoSocketHandler.configure()
    if options.client_side_worker_path:
      from clientsideworker import ClientSideWorkerSocketHandler
      ClientSideWorkerSocketHandler.configure()
    tornado.options.define = define

  def prepare(self):
    self.__pending_sockets = bind_sockets(options.port)

  def main_loop(self):
    db_connection = configured_connection()
  
    application_settings = {}
    if options.cookie_secret:
      application_settings['cookie_secret'] = options.cookie_secret
    if options.autoreload:
      application_settings['debug'] = True

    handlers = []
    if options.use_web_sockets:
      handlers.append(('%s/?([^/]?[\w\./]*)' % os.path.join(options.root, options.socket_path), TotoSocketHandler, {'db_connection': db_connection}))
    if options.client_side_worker_path:
      handlers.append((os.path.join(options.root, options.client_side_worker_path), ClientSideWorkerSocketHandler))
    if not options.event_mode == 'off':
      from toto.events import EventManager
      event_manager = EventManager.instance()
      event_manager.address = 'tcp://*:%s' % (options.event_port + self.service_id)
      event_manager.start_listening()
      for i in xrange(process_count()):
        event_manager.register_server('tcp://127.0.0.1:%s' % (options.event_port + i))
      if options.remote_event_receivers:
        for address in options.remote_event_receivers:
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
  
    server = HTTPServer(application)
    server.add_sockets(self.__pending_sockets)
    print "Starting server %d on port %s" % (self.service_id, options.port)
    IOLoop.instance().start()
