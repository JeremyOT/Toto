from threading import Thread
from traceback import format_exc
import zmq
import logging

class MessageQueue():

  def __init__(self):
    self.__handlers = {}
    self.__zmq_context = zmq.Context()
    self.__out_socket = self.__zmq_context.socket(zmq.PUSH)
    self.__thread = None
    self.__protocol = None
    self.__port = 0
    self.__interface = None
    self.on_recv = None
  
  @property
  def port(self):
    return self.__port
  
  @property
  def interface(self):
    return self.__interface
  
  @property
  def protocol(self):
    return self.__protocol

  def address(self):
    return '%s://%s:%s' % (protocol, interface, port)

  def connect_output(self, *addresses):
    for address in addresses:
      self.__socket.connect(addresses)

  def start_listening(self, on_recv=None, port=0, protocol='tcp', interface='*'):
    if self.__thread:
      return
    if on_recv:
      self.on_recv = on_recv
    self.__protocol = protocol
    self.__interface = interface
    def listen():
      context = zmq.Context()
      socket = context.socket(zmq.PULL)
      if port:
        self.__port = port
        socket.bind(self.address)
      else:
        self.__port = socket.bind_to_random_port('%s://%s', protocol, interface)
      while True:
        try:
          message = socket.recv()
          if on_recv:
            on_recv(message)
        except Exception as e:
          logging.error(format_exc())
      self.__thread = None
    self.__thread = Thread(target=listen)
    self.__thread.daemon = True
    self.__thread.start()
  
  def send(self, message):
    self.__out_socket.send(message)

  _instances = {}

  @classmethod
  def instance(cls, name='MessageQueue'):
    try:
      return cls._instances[name]
    except:
      cls._instances[name] = cls()
      return cls._instances[name]
