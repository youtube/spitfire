from distutils.core import setup

import spitfire

setup(
    name="spitfire",
    version=spitfire.__version__,
    description="text-to-python template language",
    author=spitfire.__author__,
    author_email=spitfire.__author_email__,
    license=spitfire.__license__,
    download_url="",
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
              "spitfire.runtime",
              ],
    py_modules=['yappsrt'],
    scripts=["scripts/crunner.py",
             "scripts/spitfire-compile",
             ],
     ) 
