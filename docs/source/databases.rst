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
  .. automethod:: DBConnection.remove_session

  Extending ``DBConnection``
  --------------------------

  The following methods must be implemented for a subclass
  of ``DBConnection`` to function properly:

  .. automethod:: DBConnection._remove_session
  .. automethod:: DBConnection._load_uncached_data
  .. automethod:: DBConnection._store_session
  .. automethod:: DBConnection._update_password
  .. automethod:: DBConnection._instantiate_session
  .. automethod:: DBConnection._get_account
  .. automethod:: DBConnection._store_account

  The following methods are optional:

  .. automethod:: DBConnection.clear_sessions
  .. automethod:: DBConnection._update_expiry
  .. automethod:: DBConnection._prepare_session
