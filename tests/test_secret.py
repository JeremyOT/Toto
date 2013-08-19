import unittest

from uuid import uuid4
from toto.secret import *

class TestSecret(unittest.TestCase):

  def test_password_hash(self):
    pw = uuid4().hex
    self.assertTrue(pw != password_hash(pw))
    self.assertTrue(password_hash(pw) != password_hash(pw + uuid4().hex))
    self.assertTrue(password_hash(pw) != password_hash(uuid4().hex))
    self.assertTrue(password_hash(pw) != password_hash(pw)) #check salt
  
  def test_verify_password(self):
    pw = uuid4().hex
    pw_hash = password_hash(pw)
    self.assertTrue(not verify_password('', pw_hash))
    self.assertTrue(not verify_password(pw + uuid4().hex, pw_hash))
    self.assertTrue(not verify_password(uuid4().hex, pw_hash))
    self.assertTrue(verify_password(pw, pw_hash))
