#!/usr/bin/env python

# Copyright 2007 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.


import copy
import logging
import os.path
import sys
import time
import traceback

import cStringIO as StringIO

import spitfire.compiler.compiler
import spitfire.compiler.options
import spitfire.compiler.util
import spitfire.compiler.visitor
import spitfire.runtime
import spitfire.runtime.runner
import spitfire.runtime.udn


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
  def __init__(self, compiler, options, files):
    self.compiler = compiler
    self.options = options
    self.files = files
    self._search_list = [
      {'tier1': {'tier2': ResolveCounter()}},
      {'nest': ResolveCounter()},
      ResolveCounter(),
    ]
    if options.test_input:
      self._search_list.append(
          spitfire.runtime.runner.load_search_list(options.test_input))
    self.buffer = StringIO.StringIO()
    self.start_time = 0
    self.finish_time = 0
    self.num_tests_run = 0
    self.num_tests_failed = 0

  # return a copy of the search_list for each set of tests
  @property
  def search_list(self):
    return copy.deepcopy(self._search_list)

  def run(self):
    self.begin()
    for filename in self.files:
      self.process_file(filename)
    self.end()

  def begin(self):
    self.start_time = time.time()

  def end(self):
    self.finish_time = time.time()
    print >> sys.stderr
    if self.num_tests_failed > 0:
      sys.stderr.write(self.buffer.getvalue())
    print >> sys.stderr, '-' * 70
    print >> sys.stderr, 'Ran %d tests in %0.3fs' % (
            self.num_tests_run, self.finish_time - self.start_time)
    print >> sys.stderr
    if self.num_tests_failed > 0:
      print >> sys.stderr, 'FAILED (failures=%d)' % self.num_tests_failed
      sys.exit(1)
    else:
      print >> sys.stderr, 'OK'
      sys.exit(0)

  def process_file(self, filename):
    buffer = StringIO.StringIO()
    reset_sys_modules()

    classname = spitfire.compiler.util.filename2classname(filename)
    modulename = spitfire.compiler.util.filename2modulename(filename)
    test_output_path = os.path.join(self.options.test_output,
                                    classname + '.txt')

    if self.options.verbose:
      sys.stderr.write(modulename + ' ... ')

    compile_failed = False
    if self.options.debug or self.options.compile:
      try:
        self.compiler.compile_file(filename)
      except Exception as e:
        compile_failed = True
        print >> buffer, '=' * 70
        print >> buffer, 'FAIL:', modulename, '(' + filename + ')'
        print >> buffer, '-' * 70
        traceback.print_exc(None, buffer)
      if self.options.debug:
        if 'parse_tree' in self.options.debug_flags:
          print >> buffer, "parse_tree:"
          spitfire.compiler.visitor.print_tree(self.compiler._parse_tree, output=buffer)
        if 'analyzed_tree' in self.options.debug_flags:
          print >> buffer, "analyzed_tree:"
          spitfire.compiler.visitor.print_tree(self.compiler._analyzed_tree, output=buffer)
        if 'optimized_tree' in self.options.debug_flags:
          print >> buffer, "optimized_tree:"
          spitfire.compiler.visitor.print_tree(self.compiler._optimized_tree, output=buffer)
        if 'hoisted_tree' in self.options.debug_flags:
          print >> buffer, "hoisted_tree:"
          spitfire.compiler.visitor.print_tree(self.compiler._hoisted_tree, output=buffer)
        if 'source_code' in self.options.debug_flags:
          print >> buffer, "source_code:"
          for i, line in enumerate(self.compiler._source_code.split('\n')):
            print >> buffer, '% 3s' % (i + 1), line


    test_failed = False
    if not self.options.skip_test:
      import tests

      current_output = None
      raised_exception = False
      try:
        if self.options.debug or self.options.compile:
          template_module = spitfire.compiler.util.load_module_from_src(
            self.compiler._source_code, filename, modulename)
        else:
          template_module = spitfire.runtime.import_module_symbol(modulename)
      except Exception as e:
        # An exception here means the template is unavailble; the test fails.
        test_failed = True
        raised_exception = True
        current_output = str(e)

      if not test_failed:
        try:
          template_class = getattr(template_module, classname)
          template = template_class(search_list=self.search_list)
          current_output = template.main().encode('utf8')
        except Exception as e:
          # An exception here doesn't meant that the test fails necessarily
          # since libraries don't have a class; as long as the expected output
          # matches the exception, the test passes.
          raised_exception = True
          current_output = str(e)

      if not test_failed:
        if self.options.test_accept_result:
          test_file = open(test_output_path, 'w')
          test_file.write(current_output)
          test_file.close()
        try:
          test_file = open(test_output_path)
        except IOError as e:
          # An excpetion here means that the expected output is unavailbe;
          # the test fails.
          test_failed = True
          raised_exception = True
          current_output = str(e)

      if test_failed:
        test_output = None
      else:
        test_output = test_file.read()
        if current_output != test_output:
          test_failed = True
          if self.options.debug:
            print >> buffer, "expected output:"
            print >> buffer, test_output
            print >> buffer, "actual output:"
            print >> buffer, current_output

      if compile_failed or test_failed:
        self.num_tests_failed += 1
        if self.options.verbose:
          sys.stderr.write('FAIL\n')
        else:
          sys.stderr.write('F')
        current_output_path = os.path.join(self.options.test_output,
                                           classname + '.failed')
        f = open(current_output_path, 'w')
        f.write(current_output)
        f.close()
        print >> buffer, '=' * 70
        print >> buffer, 'FAIL:', modulename, '(' + filename + ')'
        print >> buffer, '-' * 70
        print >> buffer, 'Compare expected and actual output with:'
        print >> buffer, '    diff -u', test_output_path, current_output_path
        print >> buffer, 'Show debug information for the test with:'
        test_cmd = [arg for arg in sys.argv if arg not in self.files]
        if '--debug' not in test_cmd:
          test_cmd.append('--debug')
        test_cmd = ' '.join(test_cmd)
        print >> buffer, '   ', test_cmd, filename
        if raised_exception:
          print >> buffer, '-' * 70
          print >> buffer, current_output
          traceback.print_exc(None, buffer)
        print >> buffer
        self.buffer.write(buffer.getvalue())
      else:
        if self.options.verbose:
          sys.stderr.write('ok\n')
        else:
          sys.stderr.write('.')
      self.num_tests_run += 1



if __name__ == '__main__':
  reload(sys)
  sys.setdefaultencoding('utf8')

  from optparse import OptionParser
  op = OptionParser()
  spitfire.compiler.options.add_common_options(op)
  op.add_option('-c', '--compile', action='store_true', default=False)
  op.add_option('--skip-test', action='store_true', default=False)
  op.add_option('--test-input', default='tests/input/search_list_data.pye',
                help='input data file for templates (.pkl or eval-able file)')
  op.add_option('--test-output', default='tests/output',
          help="directory for output")
  op.add_option('--test-accept-result', action='store_true', default=False,
          help='accept current code output as correct for future tests')
  op.add_option('--debug', action='store_true', default=False)
  op.add_option('--debug-flags', action='store',
                default='hoisted_tree,source_code',
                help='parse_tree, analyzed_tree, optimized_tree, hoisted_tree, source_code'
                )
  op.add_option('--enable-c-accelerator', action='store_true', default=False)
  (options, args) = op.parse_args()
  if options.debug:
    options.verbose = True
    options.debug_flags = getattr(options, 'debug_flags').split(',')
  else:
    options.debug_flags = []

  spitfire.runtime.udn.set_accelerator(
    options.enable_c_accelerator, enable_test_mode=True)

  compiler_args = (
        spitfire.compiler.compiler.Compiler.args_from_optparse(options))
  compiler = spitfire.compiler.compiler.Compiler(**compiler_args)

  test_runner = TestRunner(compiler, options, args)
  test_runner.run()
