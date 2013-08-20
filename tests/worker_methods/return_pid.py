from toto.invocation import *
import os

def invoke(worker, parameters):
  return {'pid': os.getpid()}
