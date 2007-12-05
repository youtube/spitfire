#!/usr/bin/env python

import imp
import os.path
import sys
import traceback

from pprint import pprint

import spitfire.compiler.parser
import spitfire.compiler.scanner
import spitfire.compiler.analyzer
import spitfire.compiler.optimizer
import spitfire.compiler.util
from spitfire.compiler.visitor import print_tree
analyzer = spitfire.compiler.analyzer

import spitfire.runtime.runner


def print_tree_walk(node, indent=0):
  if indent > 5:
    raise 'error'
  print '%s%s' % (' ' * indent, node)
  for n in node.child_nodes:
    print_tree_walk(n, indent + 1)


def process_file(filename, options):
  print_lines = []
  def print_output(*args):
    if options.quiet:
      print_lines.append(args)
    else:
      print >> sys.stderr, ' '.join(args)

  opt = analyzer.optimizer_map[options.optimizer_level]
  opt.update(strip_optional_whitespace=options.ignore_optional_whitespace)

  classname = spitfire.compiler.util.filename2classname(filename)
  try:
    print_output("compile", filename)
    if not options.quiet:
      print "parse_root walk"
      parse_root = spitfire.compiler.util.parse_file(filename, options.xhtml)
      #print_tree_walk(parse_root)
      #print_tree(parse_root)
    
    if not options.quiet:
      print "ast_root walk"
      ast_root = spitfire.compiler.analyzer.SemanticAnalyzer(
        classname, parse_root, options=opt).get_ast()
      print_tree(ast_root)

    if not options.quiet:
      print "optimized ast_root walk"
      spitfire.compiler.optimizer.OptimizationAnalyzer(
        ast_root, options=opt).optimize_ast()
      print_tree(ast_root)

    if not options.quiet:
      print "src_code"
      src_code = spitfire.compiler.codegen.CodeGenerator(
        ast_root, opt).get_code()
      #src_code = spitfire.compiler.util.compile_file(filename, options=opt)
      for i, line in enumerate(src_code.split('\n')):
        print '% 3s' % (i + 1), line
  except Exception, e:
    print >> sys.stderr, "FAILED:", classname, e
    raise

  if options.test:
    print_output("test", classname, '...')

    if options.test_input:
      search_list = [
        spitfire.runtime.runner.load_search_list(options.test_input)]
    else:
      search_list = []
      
    raised_exception = False
    try:
      module_name='tests.%s' % classname
      class_object = spitfire.compiler.util.load_template_file(
        filename, module_name, options=opt, xhtml=options.xhtml)
      template = class_object(search_list=search_list)
      current_output = template.main().encode('utf8')
    except Exception, e:
      current_output = str(e)
      raised_exception = True

    test_output_path = os.path.join(os.path.dirname(filename),
                    options.test_output,
                    classname + '.txt')

    if options.accept_test_result:
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
        options.test_output,
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
      
    else:
      print_output('OK')


if __name__ == '__main__':
  from optparse import OptionParser
  op = OptionParser()
  op.add_option('-t', '--test', action='store_true', default=False)
  op.add_option('--test-input')
  op.add_option('--xhtml', action='store_true')
  op.add_option('--test-output', default='output',
          help="directory for output")
  op.add_option('--accept-test-result', action='store_true', default=False,
          help='accept current code output as correct for future tests')
  op.add_option('--preserve-optional-whitespace', action='store_false',
          default=True, dest='ignore_optional_whitespace',
          help='preserve leading whitespace before a directive')
  op.add_option('-q', '--quiet', action='store_true', default=False)
  op.add_option('-O', dest='optimizer_level', type='int', default=0)
  (options, args) = op.parse_args()

  for filename in args:
    process_file(filename, options)
