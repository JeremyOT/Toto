#!/usr/bin/env python

import urllib2
import json

print urllib2.urlopen('http://localhost:8888', json.dumps({'method': 'post_message', 'parameters': {'message': 'test message, welcome to Toto'}})).read()
