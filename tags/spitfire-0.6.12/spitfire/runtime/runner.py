import os.path
import sys

import cPickle as pickle

from optparse import OptionParser


def run_template(class_object):
  parser = OptionParser()
  parser.add_option('-f', dest='filename',
                    help='data file for template search list')
  (options, args) = parser.parse_args()

  if options.filename:
    data = [load_search_list(options.filename)]
  else:
    data = []
  template = class_object(search_list=data)
  sys.stdout.write(template.main())
  
  
def load_search_list(filename):
  f = open(filename)
  ext = os.path.splitext(filename)[-1]
  if ext == '.pkl':
    data = cPickle.load(f)
  else:
    data = eval(f.read())
  return data
