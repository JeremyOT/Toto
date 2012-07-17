from pbkdf2 import crypt

def password_hash(secret):
  return crypt(password)

def verify_password(secret, pwhash):
  return pwhash == crypt(secret, pwhash)
