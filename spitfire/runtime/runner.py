# Copyright 2007 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import logging
import optparse
import os.path
import sys

import cPickle as pickle


def run_template(class_object):
    option_parser = optparse.OptionParser()
    option_parser.add_option('-f',
                             dest='filename',
                             help='data file for template search list')
    (tmpl_options, tmpl_args) = option_parser.parse_args()

    if tmpl_options.filename:
        data = [load_search_list(tmpl_options.filename)]
    else:
        data = []
    template = class_object(search_list=data)
    sys.stdout.write(template.main())


def load_search_list(filename):
    f = open(filename)
    raw_data = f.read()
    ext = os.path.splitext(filename)[-1]
    if ext == '.pkl':
        data = pickle.loads(raw_data)
    else:
        try:
            data = eval(raw_data)
        except Exception, e:
            logging.error('load_search_list\n%s', raw_data)
            raise
    return data
