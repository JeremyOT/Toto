from toto.invocation import *

def invoke(worker, parameters):
  raise TotoException(4242, 'Test Toto Exception')
