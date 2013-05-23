#!/usr/bin/python

from request import toto_request

session = {}
execfile('session.conf', session, session)

print toto_request('increment', session=session)
