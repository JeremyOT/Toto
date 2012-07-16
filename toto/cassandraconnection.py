from pycassa import ColumnFamily, ConnectionPool

"""
  A simple wrapper around a pycassa.ConnectionPool object that provides easy access and caching for ColumnFamily objects.

  Creation:
  connection = CassandraConnection(ConnectionPool('my_keyspace', ['localhost:9160']))
  connection = CassandraConnection('my_keyspace', ['localhost:9160'])

  Usage:
  cf = connection.my_column_family #Equivalent to ColumnFamily(connection.pool, 'my_column_family')
  cf = connection['my_column_family']
  cf = connection.column_families['my_column_family']
"""
class CassandraConnection():
  def __init__(self, *args, **kwargs):
    if len(args) and isinstance(args[0], ConnectionPool):
      self.pool = args[0]
    else:
      self.pool = ConnectionPool(*args, **kwargs)
    self.column_families = {}

  def __getattr__(self, name):
    return self[name]

  def __getitem__(self, name):
    try:
      return self.column_families[name]
    except:
      self.column_families[name] = ColumnFamily(self.pool, name)
      return self.column_families[name]

  def __str__(self):
    return  '<toto.cassandraconnection.CassandraConnection %d [%s]>' % (id(self), ','.join(self.column_families.keys()))

  def __repr__(self):
    return str(self)
