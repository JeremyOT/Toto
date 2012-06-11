#!/usr/bin/env python

import toto.server

if __name__ == "__main__":
  toto.server.TotoServer('event.conf').run()
