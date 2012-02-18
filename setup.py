#!/usr/bin/env python

from distutils.core import setup
from distutils.command.install import INSTALL_SCHEMES
import os

for scheme in INSTALL_SCHEMES.values():
  scheme['data'] = scheme['purelib']

template_files = []
for (path, dirs, files) in os.walk('templates'):
  template_files.append((path, [os.path.join(path, f) for f in files]))

setup(
  name='Toto',
  version='0.6.4',
  author='JeremyOT',
  author_email='',
  download_url='https://github.com/JeremyOT/Toto/zipball/master',
  license='MIT License',
  platforms=['OS X', 'Linux'],
  url='https://github.com/JeremyOT/Toto',
  packages=['toto',],
  requires=['tornado(>=2.1)',],
  provides=['toto',],
  scripts=['scripts/toto-create',],
  description='A Tornado based framework designed to accelerate web service development',
  classifiers=['License :: OSI Approved :: MIT License', 'Operating System :: POSIX'],
  data_files=template_files
  )
