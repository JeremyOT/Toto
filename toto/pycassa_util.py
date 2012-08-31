from pycassa import ColumnFamily
from itertools import islice

def get_all(self, key, column_count=100, yield_batch=False, **kwargs):
  kwargs['key'] = key
  kwargs['column_count'] = column_count
  results = self.get(**kwargs)
  result_count = len(results)
  if yield_batch:
    k = next(reversed(results))
    yield results
  else:
    for k, v in results.iteritems():
      yield k, v
  while result_count == column_count:
    kwargs['column_start'] = k
    results = self.get(**kwargs)
    result_count = len(results)
    if result_count:
      results.popitem(False)
    if yield_batch:
      k = next(reversed(results))
      yield results
    else:
      for k, v in results.iteritems():
        yield k, v

ColumnFamily.get_all = get_all

def get_columns(self, key, columns, column_count=100, yield_batch=False, **kwargs):
  kwargs['key'] = key
  kwargs['column_count'] = column_count
  index = 0
  while index < len(columns):
    kwargs['columns'] = columns[index:index + column_count]
    if yield_batch:
      yield self.get(**kwargs)
    else:
      for k, v in self.get(**kwargs).iteritems():
        yield k, v
    index += column_count

ColumnFamily.get_columns = get_columns

def xmultiget(self, keys, buffer_size=0, *args, **kwargs):
  buffer_size = buffer_size or self.buffer_size
  key_iter = iter(keys)
  key_batch = list(islice(key_iter, buffer_size))
  while key_batch:
    for k, v in self.multiget(key_batch, buffer_size=buffer_size, *args, **kwargs).iteritems():
      yield k, v
    key_batch = list(islice(key_iter, buffer_size))

ColumnFamily.xmultiget = xmultiget

def get_page(self, key, last_column=None, *args, **kwargs):
  if last_column is None:
    return self.get(key, *args, **kwargs)
  else:
    results = self.get(key, column_start=last_column, *args, **kwargs)
    try:
      del results[last_column]
    except:
      pass
    return results

ColumnFamily.get_page = get_page
