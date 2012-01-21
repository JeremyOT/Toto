#!/usr/bin/env python

from distutils.core import setup

setup(
  name='Toto',
  version='0.2',
  author='JeremyOT',
  url='https://github.com/JeremyOT/Toto',
  packages=['toto',],
  requires=['tornado(>=2.1)',],
  provides=['toto',],
  scripts=['scripts/toto-create',],
  data_files=[('templates/toto', ['templates',]),]
  )
