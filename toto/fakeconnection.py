from dbconnection import DBConnection

class FakeConnection(DBConnection):

  def __init__(self):
    self.db = None

def _store_account(self, user_id, values):
  pass

def _load_uncached_data(self, session_id):
  pass

def _get_account(self, user_id):
  pass

def _store_session(self, session_id, session_data):
  pass

def _prepare_session(self, account, session_data):
  pass

def _instantiate_session(self, session_data, session_cache):
  pass

def _update_expiry(self, session_id, session_data):
  pass

def _update_password(self, user_id, account, hashed_password):
  pass

def remove_session(self, session_id):
  pass

def clear_sessions(self, user_id):
  pass
