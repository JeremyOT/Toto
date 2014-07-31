import urllib2
import json
import hmac
from hashlib import sha1
from base64 import b64encode
from copy import copy

SERVICE_URL = 'http://127.0.0.1:9000/'

def request(method, parameters, headers={}, preprocessor=None, response_key='result', return_headers=None):
  request = {}
  request['method'] = method
  request['parameters'] = parameters
  body = json.dumps(request)
  if preprocessor:
    preprocessor(body)
  headers = copy(headers)
  headers['content-type'] = 'application/json'
  req = urllib2.Request(SERVICE_URL, body, headers)
  f = urllib2.urlopen(req)
  r = json.loads(f.read())
  if response_key:
    r = r[response_key]
  if return_headers:
    return r, f.info()
  else:
    return r

def authenticated_request(method, parameters, session_id, signing_key=None, **kwargs):
  headers = {'x-toto-session-id': session_id}
  if not signing_key:
    return request(method, parameters, headers, **kwargs)

  def gen_hmac(body):
    signature = 'POST/'+body
    headers['x-toto-hmac'] = b64encode(hmac.new(str(signing_key), signature, sha1).digest())
  return request(method, parameters, headers, gen_hmac, **kwargs)
