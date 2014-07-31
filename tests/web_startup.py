from toto.clientsessioncache import ClientCache, AESCipher

def on_start(db_connection, **kwargs):
  db_connection.set_session_cache(ClientCache(AESCipher('123456789012345612345678901234561234567890123456')))
