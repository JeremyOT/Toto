from pycassa import ColumnFamily

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
