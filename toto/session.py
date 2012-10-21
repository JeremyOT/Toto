import cPickle as pickle

class TotoAccount(object):
  '''Instances of TotoAccount provide dictionary-like access to user account properties. Unlike
  sessions, account properties are loaded directly from distinct fields in the database so if
  you're not using a schemaless database you'll need to make sure the fields (columns) exist
  in advance.
  '''

  def __init__(self, session):
    self._session = session
    self._modified_properties = set()
    self._properties = {}

  def __getitem__(self, key):
    if key not in self._properties:
      self.load_property(key)
    return key in self._properties and self._properties[key] or None

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
    '''Save any modified keys to the user account stored in the database.
    '''
    self._save_property(*self._modified_properties)
    self._modified_properties.clear()

  def load_property(self, *args):
    '''Load the properties passed to args. Properties will be dynamically loaded as they are accessed,
    but if you know you'll be referencing multiple properties, it can be faster to load them in bulk
    by passing all the keys you want to load as arguments to this method first.
    '''
    loaded = self._load_property(*args)
    for k in loaded:
      self._properties[k] = loaded[k]
    return self

  def __str__(self):
    return str({'properties': self._properties, 'modified': self._modified_properties})

  def _load_property(self, *args):
    raise Exception("Unimplemented operation: _load_property")

  def _save_property(self, *args):
    raise Exception("Unimplemented operation: _save_property")

class TotoSession(object):
  '''Instances of ``TotoSession`` provide dictionary-like access to current session variables, and the current
  account (if authenticated).
  '''
  def __init__(self, db, session_data):
    self._db = db
    self.user_id = session_data['user_id']
    self.expires = session_data['expires']
    self.session_id = session_data['session_id']
    self.state = 'state' in session_data and session_data['state'] and pickle.loads(str(session_data['state'])) or {}
    self._verified = False

  def get_account(self, *args):
    '''Load the account associated with this session (if authenticated). Session properties are
    pickled to a binary string and stored as the ``TotoSession.state`` property, so you don't need to configure your database to handle them in
    advance.
    '''
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

  def __str__(self):
    return str({'user_id': self.user_id, 'expires': self.expires, 'id': self.session_id, 'state': self.state})

  def refresh(self):
    '''Refresh the current session to the state in the database.
    '''
    raise Exception("Unimplemented operation: refresh")

  def save(self):
    '''Save the session to the database.
    '''
    raise Exception("Unimplemented operation: save")
