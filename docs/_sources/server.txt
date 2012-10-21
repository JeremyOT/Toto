Servers, Handlers and Sessions
==============================

.. automodule:: toto.server

  Server
  ------
  .. autoclass:: TotoServer
  
  The following method will normally be your only interaction with an instance of ``TotoServer``

  .. automethod:: TotoServer.run

  Handler
  -------
  .. autoclass:: toto.handler.TotoHandler

  Response paths
  ^^^^^^^^^^^^^^

  .. automethod:: toto.handler.TotoHandler.respond
  .. automethod:: toto.handler.TotoHandler.respond_raw
  .. automethod:: toto.handler.TotoHandler.on_connection_close

  Event Framework
  ^^^^^^^^^^^^^^^

  .. automethod:: toto.handler.TotoHandler.register_event_handler
  .. automethod:: toto.handler.TotoHandler.deregister_event_handler

  Sessions
  --------
  
  .. automethod:: toto.handler.TotoHandler.create_session
  .. automethod:: toto.handler.TotoHandler.retrieve_session

  The TotoSession class
  ^^^^^^^^^^^^^^^^^^^^^

  .. autoclass:: toto.session.TotoSession

  .. automethod:: toto.session.TotoSession.refresh
  .. automethod:: toto.session.TotoSession.save
  .. automethod:: toto.session.TotoSession.get_account

  The TotoAccount class
  ^^^^^^^^^^^^^^^^^^^^^

  .. autoclass:: toto.session.TotoAccount

  .. automethod:: toto.session.TotoAccount.load_property
  .. automethod:: toto.session.TotoAccount.save
