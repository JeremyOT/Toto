from toto.session import *
from copy import copy
from base64 import b64encode, b64decode

class AESCipher(object):
  '''A convenient cipher implementation for AES encryption and decryption.

     Create a new ``AESCipher`` with the given ``key`` and ``iv`` that wraps
     ``Crypto.AES`` but is reusable and thread safe. For convenience, both
     the ``key`` and ``iv`` may be provided as one string, in which case the
     last ``AES.block_size`` (16) bytes will be used for ``iv``.
  '''

  def __init__(self, key, iv=None):
    from Crypto.Cipher import AES
    self.block_size = AES.block_size
    if not iv:
      iv = key[-self.block_size:]
      key = key[:-self.block_size]
    self.aes = lambda:AES.new(key, AES.MODE_CBC, iv)

  def encrypt(self, data):
    diff = self.block_size - (len(data) % self.block_size)
    return self.aes().encrypt(data + chr(diff) * diff)

  def decrypt(self, data):
    decrypted = self.aes().decrypt(data)
    return decrypted[:-ord(decrypted[-1])]

class ClientCache(TotoSessionCache):
  '''A ``TotoSessionCache`` implementation that stores all session data with the
     client. Depending on use, the session may be sent as a header or cookie.
     ``ClientCache`` works by storing the encrypted session state in
     the session ID and decrypting it on each request. When using this method,
     it is important to keep session state small as it can add significant
     overhead to each request.

     ``cipher`` will be used to encrypt and decrypt the session data. It should
     be identical between all servers in a deployment to allow proper request
     balancing. ``cipher`` is expected to implement ``encrypt(data)`` and
     the reverse ``decrypt(data)`` both accepting and returning ``str`` objects.
  '''

  def __init__(self, cipher):
    self.cipher = cipher

  def store_session(self, session_data):
    persisted_data = copy(session_data)
    del persisted_data['session_id']
    return b64encode(self.cipher.encrypt(TotoSession.dumps(session_data)), '-_')

  def load_session(self, session_id):
    session_data = TotoSession.loads(self.cipher.decrypt(b64decode(session_id, '-_')))
    session_data['session_id'] = session_id
    return session_data

  def remove_session(self, session_id):
    pass
