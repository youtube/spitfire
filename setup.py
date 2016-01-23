# Copyright 2007 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import os.path
from setuptools import Extension
from setuptools import setup

import spitfire

setup(
    name="spitfire",
    description="text-to-python template language",
    version=spitfire.__version__,
    author=spitfire.__author__,
    author_email=spitfire.__author_email__,
    license=spitfire.__license__,
    platforms=["Posix", "MacOS X", "Windows"],
    classifiers=["Development Status :: 3 - Alpha",
                 "Intended Audience :: Developers",
                 "License :: OSI Approved :: BSD License",
                 "Programming Language :: Python",
                 "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
                 "Topic :: Software Development :: Code Generators",
                 "Topic :: Text Processing",
                 ],
    packages=["spitfire",
              "spitfire.compiler",
              "spitfire.compiler.macros",
              "spitfire.runtime",
              ],
    py_modules=['third_party.yapps2.yappsrt'],
    scripts=["scripts/crunner.py",
             "scripts/spitfire-compile",
             ],
    ext_modules=[Extension("spitfire.runtime._baked",
                           [os.path.join("spitfire", "runtime", "_baked.c")]),
                 Extension("spitfire.runtime._template",
                           [os.path.join("spitfire", "runtime", "_template.c")]),
                 Extension("spitfire.runtime._udn",
                           [os.path.join("spitfire", "runtime", "_udn.c")]),
                 ],
     )
