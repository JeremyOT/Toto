.. currentmodule:: toto.events

Events
======

.. automodule:: toto.events

  .. autoclass:: EventManager
  .. automethod:: EventManager.instance
  .. automethod:: EventManager.start_listening

  Remote Servers
  --------------

  .. automethod:: EventManager.register_server
  .. automethod:: EventManager.remove_server
  .. automethod:: EventManager.remove_all_servers
  .. automethod:: EventManager.refresh_server_queue

  Handlers
  --------

  .. automethod:: EventManager.register_handler
  .. automethod:: EventManager.remove_handler

  Transmission
  ------------
  
  .. automethod:: EventManager.send_to_server
  .. automethod:: EventManager.send
