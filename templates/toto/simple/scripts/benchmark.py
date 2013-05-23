#!/usr/bin/env python

from create import create_account
from request import toto_request
from uuid import uuid4
from time import time

def checkresponse(response):
  if 'error' in response:
    print response['error']
    exit()
  return response

def verify_count(response, n):
  response = checkresponse(response)
  if n != response['result']['count']:
    print 'Counter not incrementing, expected %s got %s' % (n, response['result']['count'])
    print response
    exit()
  return response


count = int(raw_input('How many requests? (default 1000)') or 1000)
user_id = uuid4().hex
password = uuid4().hex
print "user_id: %s password: %s" % (user_id, password)
print checkresponse(create_account(user_id, password))
session = {}
execfile('session.conf', session, session)
start = time()
for i in xrange(1, count + 1):
  verify_count(toto_request('increment', session=session), i)
total = time() - start
print 'Ran %s successful requests in %s seconds' % (count, total)
