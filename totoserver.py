#!/usr/bin/python

from tornado.web import *
from tornado.ioloop import *
import json
import hashlib
import hmac
import toto
from toto.exceptions import *
from toto.invocation import *
from time import time
from tornado.options import define, options
import base64

class TotoHandler(RequestHandler):

  SUPPORTED_METHODS = ["POST",]

  def initialize(self, connection):
    self.connection = connection

  """
    Lookup method by name: a.b.c loads api/a/b/c.py
  """
  def __get_method(self, method_name):
    method_path = method_name.split('.')
    method = toto
    while method_path:
      method = getattr(method, method_path.pop(0))
    return method.invoke

  @asynchronous
  def post(self):
    self.session = None
    self.__method = None
    headers = self.request.headers
    response = {}
    try:
      if 'x-toto-session-id' in headers:
        self.session = self.connection.retrieve_session(headers['x-toto-session-id'], 'x-toto-hmac' in headers and headers['x-toto-hmac'] or None, self.request.body)
      body = json.loads(self.request.body)
      if 'method' not in body:
        raise TotoException(ERROR_MISSING_METHOD, "Missing method.")
      self.__method = self.__get_method(body['method'])
      if not 'parameters' in body:
        raise TotoException(ERROR_MISSING_PARAMS, "Missing parameters.")
      if not self.session and hasattr(self.__method, 'authenticated'):
        raise TotoException(ERROR_NOT_AUTHORIZED, "Not authorized")
      response['result'] = self.__method(self, body['parameters'])
    except TotoException as e:
      response['error'] = e.__dict__
    except Exception as e:
      response['error'] = TotoException(ERROR_SERVER, str(e)).__dict__
    if response is not None:
      response_body = json.dumps(response)
      if self.session:
        self.set_header('x-toto-hmac', base64.b64encode(hmac.new(str(self.session.user_id), response_body, hashlib.sha1).digest()))
      self.write(response_body)
    if not hasattr(self.__method, 'asynchronous'):
      self.finish()

  def on_connection_close(self):
    if hasattr(self.__method, 'on_connection_close'):
      self.__method.on_connection_close();

define("database", metavar='mysql|mongodb', default="mongodb", help="the database driver to use (default 'mongodb')")
define("mysql_host", default="localhost:3306", help="MySQL database 'host:port' (default 'localhost:3306')")
define("mysql_database", type=str, help="Main MySQL schema name")
define("mysql_user", type=str, help="Main MySQL user")
define("mysql_password", type=str, help="Main MySQL user password")
define("mongodb_host", default="localhost", help="MongoDB host (default 'localhost')")
define("mongodb_port", default=27017, help="MongoDB port (default 27017)")
define("mongodb_database", default="toto_server", help="MongoDB database (default 'toto_server')")
define("port", default=8888, help="The port to run this server on (default 8888)")

tornado.options.parse_config_file("toto.conf")
tornado.options.parse_command_line()

connection = None
if options.database == "mongodb":
  from mongodbconnection import MongoDBConnection
  connection = MongoDBConnection(options.mongodb_host, options.mongodb_port, options.mongodb_database)
elif options.database == "mysql":
  from mysqldbconnection import MySQLdbConnection
  connection = MySQLdbConnection(options.mysql_host, options.mysql_database, options.mysql_user, options.mysql_password)

application = Application([
  (r"/", TotoHandler, {'connection': connection}),
])

if __name__ == "__main__":
  application.listen(options.port)
  print "Starting server on port %s." % options.port
  IOLoop.instance().start()

