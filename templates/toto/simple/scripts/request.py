import urllib2
import json
import hmac
import hashlib
import time
import base64
from sys import stdin

def toto_request(method, params={}, session={}):
  request = {}
  request['method'] = method
  request['parameters'] = params
  headers = {'content-type': 'application/json'}
  body = json.dumps(request)
  if session.get('session_id'):
    headers['x-toto-session-id'] = session['session_id']
    headers['x-toto-hmac'] = base64.b64encode(hmac.new(session['user_id'], body, hashlib.sha1).digest())
  req = urllib2.Request('http://localhost:8888/', body, headers)
  f = urllib2.urlopen(req)
  return json.loads(f.read())

