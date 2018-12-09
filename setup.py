#!/usr/bin/env python
##
## Name:     setup.py
## Purpose:  Install the scrubby tag-soup parser module.
##
## Copyright (C) 2009, Michael J. Fromberger, All Rights Reserved.
##
## Standard usage:  python setup.py install
##
from distutils.core import setup
from scrubby import __version__ as lib_version

setup(name = 'scrubby',
      version = lib_version,
      description = 'Tag-soup parser for HTML and similar markup languages',
      long_description = """
This module implements a simple but robust "tag-soup" style parser for
markup languages like HTML, XML, and SGML.  Unlike strict parsers, scrubby
will not choke on bad markup, although the quality of the results will vary
directly with the quality of the input.

The module has been tested with Python 2.6, 2.7, and 3.1.""",
      author = 'M. J. Fromberger',
      author_email = "michael.j.fromberger@gmail.com",
      url = 'http://spinning-yarns.org/michael/',
      classifiers = ['Development Status :: 5 - Production/Stable',
                     'Intended Audience :: Developers',
                     'License :: OSI Approved :: MIT License',
                     'Operating System :: OS Independent',
                     'Programming Language :: Python',
                     'Topic :: Text Processing :: Markup :: HTML',
                     'Topic :: Text Processing :: Markup',
                     'Topic :: Software Development :: Libraries'],
      py_modules = ['scrubby'],
      scripts = ['scrub.py'],
      )

# Here there be dragons
