#!/usr/bin/env python

import copy
import imp
import logging
import os.path
import sys
import traceback

from pprint import pprint

import spitfire.compiler.parser
import spitfire.compiler.scanner
import spitfire.compiler.analyzer
import spitfire.compiler.optimizer
import spitfire.compiler.util
import spitfire.runtime.runner
import spitfire.runtime.udn

from spitfire.compiler import analyzer
from spitfire.compiler.visitor import print_tree
from spitfire.compiler.util import Compiler


# use this resolver so that we don't call resolve tester attributes twice
# automatically
spitfire.runtime.udn.resolve_udn = spitfire.runtime.udn.resolve_udn_prefer_attr

# this class let's me check if placeholder caching is working properly by
# tracking the number of accesses for a single key
class ResolveCounter(object):
  def __init__(self):
    self._dict = {}

  @property
  def resolve_x(self):
    return self._get_item('resolve_x')

  @property
  def resolve_y(self):
    return self._get_item('resolve_y')
  
  def _get_item(self, key):
    if key in self._dict:
      self._dict[key] += 1
    else:
      self._dict[key] = 1
    return '%s%s' % (key, self._dict[key])

  def __contains__(self, key):
    return key.startswith('resolve')
  
  def __getitem__(self, key):
    if not key.startswith('resolve'):
      raise KeyError(key)
    return self._get_item(key)
    
  def __getattr__(self, key):
    if not key.startswith('resolve'):
      raise AttributeError(key)
    return self._get_item(key)


sys_modules = sys.modules.keys()
def reset_sys_modules():
  for key in sys.modules.keys():
    if key not in sys_modules:
      del sys.modules[key]

class TestRunner(object):
  def __init__(self, compiler, options):
    self.compiler = compiler
    self.options = options
    if options.test_input:
      self._search_list = [
        spitfire.runtime.runner.load_search_list(options.test_input),
        {'tier1': {'tier2': ResolveCounter()}},
        {'nest': ResolveCounter()},
        ResolveCounter(),
        ]
    else:
      self._search_list = []

  # return a copy of the search_list for each set of tests
  @property
  def search_list(self):
    return copy.deepcopy(self._search_list)

  def process_file(self, filename):
    print_lines = []
    def print_output(*args):
      if options.quiet:
        print_lines.append(args)
      else:
        print >> sys.stderr, ' '.join(args)

    print_output("processing", filename)
    reset_sys_modules()
    classname = spitfire.compiler.util.filename2classname(filename)
    module_name = 'tests.%s' % classname
    if not self.options.quiet or self.options.compile:
      try:
        self.compiler.compile_file(filename)
      except Exception, e:
        print >> sys.stderr, 'compile FAILED:', filename, e
        raise
    if not self.options.quiet:
      if 'parse_tree' in self.options.debug_flags:
        print "parse_tree:"
        print_tree(self.compiler._parse_tree)
      if 'analyzed_tree' in self.options.debug_flags:
        print "analyzed_tree:"
        print_tree(self.compiler._analyzed_tree)
      if 'optimized_tree' in self.options.debug_flags:
        print "optimized_tree:"
        print_tree(self.compiler._optimized_tree)
      if 'hoisted_tree' in self.options.debug_flags:
        print "hoisted_tree:"
        print_tree(self.compiler._hoisted_tree)
      if 'source_code' in self.options.debug_flags:
        print "source_code:"
        for i, line in enumerate(self.compiler._source_code.split('\n')):
          print '% 3s' % (i + 1), line
    

    if self.options.test:
      print_output("test", classname, '...')
      import tests

      raised_exception = False

      try:
        if not self.options.quiet or self.options.compile:
          template_module = spitfire.compiler.util.load_module_from_src(
            self.compiler._source_code, filename, module_name)
        else:
          template_module = spitfire.runtime.import_module_symbol(module_name)
      except Exception, e:
        print "dynamic import error"
        print filename, module_name
        raise

      try:
        template_class = getattr(template_module, classname)
        template = template_class(search_list=self.search_list)
        current_output = template.main().encode('utf8')
      except Exception, e:
        if not self.options.quiet:
          logging.exception("test error:")
        current_output = str(e)
        raised_exception = True

      test_output_path = os.path.join(os.path.dirname(filename),
                      self.options.test_output,
                      classname + '.txt')

      if self.options.accept_test_result:
        test_file = open(test_output_path, 'w')
        test_file.write(current_output)
        test_file.close()

      try:
        test_file = open(test_output_path)
      except IOError, e:
        print "current output:"
        print current_output
        raise

      test_output = test_file.read()
      if current_output != test_output:
        current_output_path = os.path.join(
          os.path.dirname(filename),
          self.options.test_output,
          classname + '.failed')
        f = open(current_output_path, 'w')
        f.write(current_output)
        f.close()
        for line in print_lines:
          print >> sys.stderr, ' '.join(line)
        print >> sys.stderr, "FAILED:", classname
        print >> sys.stderr, '  diff -u', test_output_path, current_output_path
        print >> sys.stderr, '  %s -t' % sys.argv[0], filename
        if raised_exception:
          print >> sys.stderr, current_output
          traceback.print_exc(raised_exception)
      else:
        print_output('OK')


if __name__ == '__main__':
  from optparse import OptionParser
  op = OptionParser()
  spitfire.compiler.util.add_common_options(op)
  op.add_option('-c', '--compile', action='store_true', default=False)
  op.add_option('-t', '--test', action='store_true', default=False)
  op.add_option('--test-input')
  op.add_option('--test-output', default='output',
          help="directory for output")
  op.add_option('--accept-test-result', action='store_true', default=False,
          help='accept current code output as correct for future tests')
  op.add_option('-q', '--quiet', action='store_true', default=False)
  op.add_option('-D', dest='debug_flags', action='store',
                default='hoisted_tree,source_code',
                help='parse_tree, analyzed_tree, optimized_tree, hoisted_tree, source_code'
                )
  (options, args) = op.parse_args()
  setattr(options, 'debug_flags', getattr(options, 'debug_flags').split(','))

  compiler_args = Compiler.args_from_optparse(options)
  compiler = Compiler(**compiler_args)
  
  test_runner = TestRunner(compiler, options)
  for filename in args:
    test_runner.process_file(filename)
