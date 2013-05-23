.. currentmodule:: toto.dbconnection

Database Connections
====================

.. automodule:: toto.dbconnection

  .. autoclass:: DBConnection

  Accounts and Sessions
  ---------------------

  .. automethod:: DBConnection.create_account
  .. automethod:: DBConnection.create_session
  .. automethod:: DBConnection.retrieve_session
  .. automethod:: DBConnection.remove_session
  .. automethod:: DBConnection.clear_sessions
  .. automethod:: DBConnection.change_password
  .. automethod:: DBConnection.generate_password
  .. automethod:: DBConnection.set_session_cache
  .. automethod:: DBConnection._load_session_data
  .. automethod:: DBConnection._load_uncached_data
  .. automethod:: DBConnection._cache_session_data
