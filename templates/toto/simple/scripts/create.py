#!/usr/bin/python

from sys import stdin
from request import toto_request

def create_account(user_id, password):
  response = toto_request('account.create', {'user_id': user_id, 'password': password})
  if 'result' in response:
    with open('session.conf', 'wb') as session_file:
      session_file.write("session_id='%s'\n" % response['result']['session_id'])
      session_file.write("user_id='%s'\n" % response['result']['user_id'])
  return response

if __name__ == '__main__':
  print "Enter your username"
  user_id = stdin.readline().strip()
  print "Enter your password"
  password = stdin.readline().strip()
  print create_account(user_id, password)
