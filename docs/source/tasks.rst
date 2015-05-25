.. currentmodule:: toto.tasks

Task Queues
===========

.. automodule:: toto.tasks

  .. autoclass:: TaskQueue
  .. automethod:: TaskQueue.instance

  Tasks
  -----

  .. automethod:: TaskQueue.add_task
  .. automethod:: TaskQueue.yield_task
  .. automethod:: TaskQueue.run
  .. automethod:: TaskQueue.__len__

  AwaitableInstance
  ------------

  .. autoclass:: AwaitableInstance

  InstancePool
  ------------

  .. autoclass:: InstancePool

  .. automethod:: InstancePool.await
  .. automethod:: InstancePool.instance
  .. automethod:: InstancePool.transaction
  .. automethod:: InstancePool.async_transaction
  .. automethod:: InstancePool.await_transaction
