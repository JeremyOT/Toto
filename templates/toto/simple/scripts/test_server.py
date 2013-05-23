#!/usr/bin/env python

from create import create_account
from login import login
from request import toto_request
from uuid import uuid4

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

user_id = uuid4().hex
password = uuid4().hex
print "user_id: %s password: %s" % (user_id, password)

print checkresponse(create_account(user_id, password))
session = {}
execfile('session.conf', session, session)
print verify_count(toto_request('increment', session=session), 1)
print verify_count(toto_request('increment', session=session), 2)
print verify_count(toto_request('increment', session=session), 3)
're-authenticate'
print checkresponse(login(user_id, password))
session = {}
execfile('session.conf', session, session)
print verify_count(toto_request('increment', session=session), 1)
print verify_count(toto_request('increment', session=session), 2)
print verify_count(toto_request('increment', session=session), 3)
print 'new user'
user_id = uuid4().hex
password = uuid4().hex
print "user_id: %s password: %s" % (user_id, password)
print checkresponse(create_account(user_id, password))
session = {}
execfile('session.conf', session, session)
print verify_count(toto_request('increment', session=session), 1)
print verify_count(toto_request('increment', session=session), 2)
print verify_count(toto_request('increment', session=session), 3)
're-authenticate'
print checkresponse(login(user_id, password))
session = {}
execfile('session.conf', session, session)
print verify_count(toto_request('increment', session=session), 1)
print verify_count(toto_request('increment', session=session), 2)
print verify_count(toto_request('increment', session=session), 3)
print 'Session storage ok'
