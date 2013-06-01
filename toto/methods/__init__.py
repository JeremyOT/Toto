'''Toto includes some built-in methods to support frequently used functionality.
These methods can be included in your method module by importing them into the
module scope like this::

  #main methods module __init__.py
  import toto.methods.account.create as account_create

  #method.account module
  import toto.methods.account.create as create

In the above examples, Toto's built in ``account.create`` method can be called from
your method module as ``account_create`` and ``account.create`` respecively.
'''

import account
import client_error
