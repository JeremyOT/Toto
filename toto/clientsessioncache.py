import hmac
import os
from hashlib import sha1
from toto.session import *
from copy import copy
from base64 import b64encode, b64decode

HMAC_ALGORITHM = sha1
HMAC_SIZE = HMAC_ALGORITHM().digest_size
PREFIX_PADDING_SIZE=16

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

  def __init__(self, cipher, hmac_key):
    self.cipher = cipher
    self.hmac_key = hmac_key

  def hmac(self, data):
    return hmac.new(self.hmac_key, data, HMAC_ALGORITHM).digest()

  def store_session(self, session_data):
    persisted_data = copy(session_data)
    del persisted_data['session_id']
    encrypted = self.cipher.encrypt(os.urandom(PREFIX_PADDING_SIZE) + TotoSession.dumps(session_data))
    return b64encode(encrypted + self.hmac(encrypted), '-_')

  def load_session(self, session_id):
    raw = b64decode(session_id, '-_')
    encrypted = raw[:-HMAC_SIZE]
    if self.hmac(encrypted) != raw[-HMAC_SIZE:]:
      raise TotoException(-1, 'Invalid session HMAC')
    data = self.cipher.decrypt(encrypted)
    session_data = TotoSession.loads(data[PREFIX_PADDING_SIZE:])
    session_data['session_id'] = session_id
    return session_data

  def remove_session(self, session_id):
    pass
