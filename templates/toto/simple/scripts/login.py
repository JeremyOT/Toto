#!/usr/bin/python

import urllib2
import json
import hmac
import hashlib
import time
import base64
from sys import stdin
from bson import BSON

print "Enter your username"
user_id = stdin.readline().strip()
print "Enter your password"
password = stdin.readline().strip()

request = {}
request['method'] = 'account.login'
request['parameters'] = {
  'user_id': user_id,
  'password': password
}
headers = {'content-type': 'application/bson'}

body = BSON.encode(request)

req = urllib2.Request('http://localhost:8888/', body, headers)
f = urllib2.urlopen(req)
response = BSON(f.read()).decode()

print response

with open('session.conf', 'wb') as session_file:
  session_file.write("session_id='%s'\n" % response['result']['session_id'])
  session_file.write("user_id='%s'\n" % response['result']['user_id'])

