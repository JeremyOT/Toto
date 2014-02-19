#!/usr/bin/env python

from distutils.core import setup
from distutils.command.install import INSTALL_SCHEMES
import os

for scheme in INSTALL_SCHEMES.values():
  scheme['data'] = scheme['purelib']

template_files = []
for (path, dirs, files) in os.walk('templates'):
  template_files.extend([os.path.join('..', path, f) for f in files])

setup(
  name='Toto',
  version='0.12.5',
  author='JeremyOT',
  author_email='',
  download_url='https://github.com/JeremyOT/Toto/zipball/master',
  license='MIT License',
  platforms=['OS X', 'Linux'],
  url='http://toto.li',
  packages=['toto','toto.methods','toto.methods.account'],
  requires=['tornado(>=3.2)',],
  install_requires=['tornado>=3.2',],
  provides=['toto',],
  scripts=['scripts/toto-create',],
  description='A Tornado based framework designed to accelerate web service development',
  long_description='Documentation is available at http://toto.li/docs/',
  classifiers=['License :: OSI Approved :: MIT License', 'Operating System :: POSIX'],
  package_data={'toto': template_files}
  )

print """
*****************************************************************************

By default, Toto will not connect to a database. Connect to a database with
the --database option. Database functionality requires the following modules:

  pbkdf2>=1.3

  MySQL: MySQL-python>=1.2.3, torndb>=0.1
  Redis: redis>=2.4.12, hiredis>=0.1.1 (optional)
  Postres: psycopg2>=2.4.5
  MongoDB: pymongo>=2.1

Toto's event and worker frameworks require pyzmq>=2.2.0

*****************************************************************************
"""
