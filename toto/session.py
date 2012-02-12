import cPickle as pickle

class TotoSession():
  _verified = False
  user_id = None
  session_id = None
  expires = 0
  state = {}
  _db = None
  
  def __init__(self, db, session_data):
    self._db = db
    self.user_id = session_data['user_id']
    self.expires = session_data['expires']
    self.session_id = session_data['session_id']
    self.state = 'state' in session_data and session_data['state'] and pickle.loads(str(session_data['state'])) or {}

  def __getitem__(self, key):
    return key in self.state and self.state[key] or None
  
  def __setitem__(self, key, value):
    self.state[key] = value

  def __delitem__(self, key):
    if key in self.state:
      del self.state[key]

  def __iter__(self):
    return self.state.__iter__()

  def iterkeys():
    return self.__iter__()

  def __contains__(self, key):
    return key in self.state

  def refresh(self):
    raise Exception("Unimplemented operation: refresh")

  def save(self):
    raise Exception("Unimplemented operation: save")
