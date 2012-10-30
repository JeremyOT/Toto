from dbconnection import DBConnection


class FakeConnection(DBConnection):

  def __init__(self):
    self.db = None

  def create_account(self, user_id, password, additional_values={}, **values):
    pass

  def create_session(self, user_id=None, password=None):
    return None

  def retrieve_session(self, session_id, hmac_data=None, data=None):
    return None

  def remove_session(self, session_id):
    pass

  def clear_sessions(self, user_id):
    pass

  def change_password(self, user_id, password, new_password):
    pass

  def generate_password(self, user_id):
    return None
