class FakeConnection():

  def __init__(self):
    self.db = None

  def retrieve_session(self, *args):
    return None

