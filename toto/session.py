import cPickle as pickle

class TotoAccount():
  _session = None
  _modified_properties = set()
  _properties = {}

  def __init__(self, session):
    self._session = session

  def __getitem__(self, key):
    if key not in self._properties:
      self.load_property(key)
    return self._properties[key]

  def __setitem__(self, key, value):
    self._properties[key] = value
    self._modified_properties.add(key)

  def __contains__(self, key):
    return key in self._properties

  def __iter__(self):
    return self._properties.__iter__()

  def iterkeys(self):
    return self.__iter__()

  def save(self):
    self.save_property(*self._modified_properties)

  def load_property(self, *args):
    loaded = self._load_property(*args)
    for k in loaded:
      self._properties[k] = loaded[k]
    return self

  def _load_property(self, *args):
    raise Exception("Unimplemented operation: _load_property")

  def _save_property(self, *args):
    raise Exception("Unimplemented operation: _save_property")

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

  def get_account(self, *args):
    raise Exception("Unimplemented operation: get_account")

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
