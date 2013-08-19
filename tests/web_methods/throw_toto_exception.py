from toto.invocation import *

def invoke(handler, parameters):
  raise TotoException(4242, 'Test Toto Exception')
