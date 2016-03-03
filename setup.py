# Copyright 2007 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import os.path
import platform
from setuptools import Extension
from setuptools import setup

import spitfire

NAME = 'spitfire'

DESCRIPTION = 'text-to-python template language'

VERSION = spitfire.__version__

AUTHOR = spitfire.__author__

AUTHOR_EMAIL = spitfire.__author_email__

LICENSE = spitfire.__license__

PLATFORMS = ['Posix', 'MacOS X', 'Windows']

CLASSIFIERS = ['Development Status :: 3 - Alpha',
               'Intended Audience :: Developers',
               'License :: OSI Approved :: BSD License',
               'Programming Language :: Python',
               'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
               'Topic :: Software Development :: Code Generators',
               'Topic :: Text Processing']

PACKAGES = ['spitfire',
            'spitfire.compiler',
            'spitfire.compiler.macros',
            'spitfire.runtime']

PY_MODULES = ['third_party.yapps2.yappsrt']

SCRIPTS = ['scripts/crunner.py', 'scripts/spitfire-compile']

EXT_MODULES = [Extension('spitfire.runtime._baked',
                         [os.path.join('spitfire', 'runtime', '_baked.c')]),
               Extension('spitfire.runtime._template',
                         [os.path.join('spitfire', 'runtime', '_template.c')]),
               Extension('spitfire.runtime._udn',
                         [os.path.join('spitfire', 'runtime', '_udn.c')])]
# Disable C extensions for PyPy.
if platform.python_implementation() == 'PyPy':
    EXT_MODULES = None

setup(name=NAME,
      description=DESCRIPTION,
      version=VERSION,
      author=AUTHOR,
      author_email=AUTHOR_EMAIL,
      license=LICENSE,
      platforms=PLATFORMS,
      classifiers=CLASSIFIERS,
      packages=PACKAGES,
      py_modules=PY_MODULES,
      scripts=SCRIPTS,
      ext_modules=EXT_MODULES)
