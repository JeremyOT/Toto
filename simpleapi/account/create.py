import time
import login
from simpleapi.exceptions import *

def invoke(handler, params):
  handler.connection.create_account(params['user_id'], params['password'])
  return login.invoke(handler, params)
