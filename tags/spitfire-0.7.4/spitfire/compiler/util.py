import copy
import logging
import new
import os.path
import re
import sys

import spitfire.compiler.analyzer
import spitfire.compiler.codegen
import spitfire.compiler.optimizer
import spitfire.compiler.parser
import spitfire.compiler.scanner
import spitfire.compiler.xhtml2ast

from spitfire import runtime
from spitfire.compiler import analyzer
from spitfire.compiler import ast
from spitfire.compiler import codegen

valid_identfier = re.compile('[_a-z]\w*', re.IGNORECASE)

def filename2classname(filename):
  classname = os.path.splitext(
    os.path.basename(filename))[0].lower().replace('-', '_')
  if not valid_identfier.match(classname):
    raise SyntaxError(
      'filename "%s" must yield valid python identifier: %s' % (filename,
                                                                classname))
  return classname


# @return abstract syntax tree rooted on a TemplateNode
def parse(src_text, rule='goal'):
  parser = spitfire.compiler.parser.SpitfireParser(
    spitfire.compiler.scanner.SpitfireScanner(src_text))
  return spitfire.compiler.parser.wrap_error_reporter(parser, rule)

def parse_file(filename, xspt_mode=False):
  return parse_template(read_template_file(filename), xspt_mode)

def parse_template(src_text, xspt_mode=False):
  if xspt_mode:
    parser = spitfire.compiler.xhtml2ast.XHTML2AST()
    return parser.parse(src_text)
  else:
    return parse(src_text)


def read_template_file(filename):
  f = open(filename, 'r')
  try:
    return f.read().decode('utf8')
  finally:
    f.close()


def read_function_registry(filename):
  f = open(filename)
  function_registry = {}
  try:
    for line in f:
      line = line.strip()
      if not line:
        continue
      if line.startswith('#'):
        continue
      
      alias, fq_name = line.split('=')
      fq_name = fq_name.strip()
      try:
        method = runtime.import_module_symbol(fq_name)
      except ImportError:
        logging.warning('unable to import function registry symbol %s', fq_name)
        method = None
                        
      function_registry[alias.strip()] = fq_name, method
    return function_registry
  finally:
    f.close()
    
    
# compile a text file into a template object
# this won't recursively import templates, it's just a convenience in the case
# where you need to create a fresh object directly from raw template file
def load_template_file(filename, module_name=None,
                       options=spitfire.compiler.analyzer.default_options,
                       xspt_mode=False,
                       compiler_options=None):
  c = Compiler(analyzer_options=options, xspt_mode=xspt_mode)
  if compiler_options:
    for k, v in compiler_options.iteritems():
      setattr(c, k, v)
  class_name = filename2classname(filename)
  if not module_name:
    module_name = class_name

  src_code = c.compile_file(filename)
  module = load_module_from_src(src_code, filename, module_name)
  return getattr(module, class_name)

def load_template(template_src, template_name,
                  options=spitfire.compiler.analyzer.default_options,
                  compiler_options=None):
  class_name = filename2classname(template_name)
  filename = '<%s>' % class_name
  module_name = class_name
  c = Compiler(analyzer_options=options)
  if compiler_options:
    for k, v in compiler_options.iteritems():
      setattr(c, k, v)
  src_code = c.compile_template(template_src, class_name)
  module = load_module_from_src(src_code, filename, module_name)
  return getattr(module, class_name)


# a helper method to import a template without having to save it to disk
def load_module_from_src(src_code, filename, module_name):
  module = new.module(module_name)
  sys.modules[module_name] = module

  bytecode = compile(src_code, filename, 'exec')
  exec bytecode in module.__dict__
  return module

class CompilerError(Exception):
  pass

class Compiler(object):
  setting_names = [
    'base_extends_package',
    'debug_flags',
    'enable_filters',
    'extract_message_catalogue',
    'function_registry_file',
    'ignore_optional_whitespace',
    'locale',
    'message_catalogue_file',
    'normalize_whitespace',
    'optimizer_level',
    'optimizer_flags',
    'output_directory',
    'xspt_mode',
    ]

  @classmethod
  def args_from_optparse(cls, options):
    settings = {}
    for name in cls.setting_names:
      if hasattr(options, name):
        settings[name] = getattr(options, name)
    return settings
  
  # settings - arbitrary dictionary of values, probably from the command line
  def __init__(self, **kargs):
    # record transient state of the compiler
    self.src_filename = None
    self.output_directory = ''
    self.xspt_mode = False
    self.write_file = False
    self.analyzer_options = None

    self.optimizer_level = 0
    self.optimizer_flags = []
    self.debug_flags = []
    self.ignore_optional_whitespace = False
    self.normalize_whitespace = False
    
    self.base_extends_package = None
    self.message_catalogue = None
    self.message_catalogue_file = None
    self.extract_message_catalogue = False
    self.locale = None

    self.enable_filters = True
    # the function registry is for optimized access to 'first-class' functions
    # things that get accessed all the time that should be speedy
    self.function_registry_file = None
    self.function_name_registry = {}
    self.macro_registry = {}

    self._parse_tree = None
    self._analyzed_tree = None
    self._optimized_tree = None
    self._hoisted_tree = None
    self._source_code = None

    for key, value in kargs.iteritems():
      setattr(self, key, value)
    
    if self.analyzer_options is None:
      self.analyzer_options = analyzer.optimizer_map[self.optimizer_level]
      self.analyzer_options.ignore_optional_whitespace = self.ignore_optional_whitespace
      self.analyzer_options.normalize_whitespace = self.normalize_whitespace

    # slightly crappy code to support turning flags on and off from the
    # command line - probably should go in analyzer options?
    for flag_name in self.optimizer_flags:
      flag_name = flag_name.lower().replace('-', '_')
      flag_value = True
      if flag_name.startswith('no_'):
        flag_name = flag_name[3:]
        flag_value = False
      if type(getattr(self.analyzer_options, flag_name, None)) == bool:
        setattr(self.analyzer_options, flag_name, flag_value)
      else:
        logging.warning('unknown optimizer flag: %s', flag_name)

    if self.function_registry_file:
      self.function_name_registry = read_function_registry(
        self.function_registry_file)

    # register macros before the first pass by any SemanticAnalyzer
    # this is just a default to give an example - it's not totally functional
    # fixme: nasty time to import - but does break weird cycle
    import spitfire.compiler.macros.i18n
    self.register_macro('macro_i18n', spitfire.compiler.macros.i18n.macro_i18n)
    self.register_macro('macro_function_i18n',
                        spitfire.compiler.macros.i18n.macro_function_i18n)

  # take an AST and generate code from it - this will run the analysis phase
  # this doesn't have the same semantics as python's AST operations
  # it would be good to have a reason for the inconsistency other than
  # laziness or stupidity
  def _compile_ast(self, parse_root, classname):
    # copy if we are debugging
    if self.debug_flags:
      parse_root = copy.deepcopy(parse_root)

    self._analyzed_tree = analyzer.SemanticAnalyzer(
      classname, parse_root, self.analyzer_options, self).get_ast()


    # keep a copy of the tree for debugging purposes
    if self.debug_flags:
      self._optimized_tree = copy.deepcopy(self._analyzed_tree)
    else:
      self._optimized_tree = self._analyzed_tree
      
    spitfire.compiler.optimizer.OptimizationAnalyzer(
      self._optimized_tree, self.analyzer_options, self).optimize_ast()

    if self.debug_flags:
      self._hoisted_tree = copy.deepcopy(self._optimized_tree)
    else:
      self._hoisted_tree = self._optimized_tree
      
    spitfire.compiler.optimizer.FinalPassAnalyzer(
      self._hoisted_tree, self.analyzer_options, self).optimize_ast()
    
    self._source_code = codegen.CodeGenerator(
      self._hoisted_tree, self.analyzer_options).get_code()
    return self._source_code

  def _reset(self):
    self._parse_tree = None
    self._analyzed_tree = None
    self._optimized_tree = None
    self._hoisted_tree = None
    self._source_code = None
    
  def compile_template(self, src_text, classname):
    self._reset()
    self._parse_tree = parse_template(src_text, self.xspt_mode)
    return self._compile_ast(self._parse_tree, classname)

  def compile_file(self, filename):
    self.src_filename = filename
    self.classname = filename2classname(filename)
    src_text = read_template_file(filename)
    src_code = self.compile_template(src_text, self.classname)
    if self.write_file:
      self.write_src_file(src_code)
    return src_code

  def write_src_file(self, src_code):
    outfile_name = '%s.py' % self.classname
    relative_dir = os.path.dirname(self.src_filename)
    if self.output_directory and os.path.isabs(relative_dir):
      raise CompilerError("can't mix output_directory and absolute paths")
    
    outfile_path = os.path.join(self.output_directory, relative_dir,
                                outfile_name)
    outfile = open(outfile_path, 'w')
    outfile.write(src_code)
    outfile.close()

  # macros could be handy - and they are complex enough that they should be
  # put somewhere else. this registry allows them to be implemented just about
  # anywhere.
  #
  # macro functions look like:
  # def macro_handler(macro_node, arg_map)
  # arg_map is a dictionary of names to values specified as parameters to the
  # macro by the template source. they are limited to literal values right now.
  def register_macro(self, name, function):
    self.macro_registry[name] = function



# convert and extends path to a file path
def extends2path(class_extend):
  return class_extend.replace('.', '/') + ".spt"
  

def validate_path(option, opt_str, path, parser):
  path = os.path.abspath(os.path.expanduser(path))
  setattr(parser.values, option.dest, path)

# standard options to any compiler front-end
# @op option_parser, this object will be modified
def add_common_options(op):
  op.add_option('--preserve-optional-whitespace', action='store_false',
                default=True, dest='ignore_optional_whitespace',
                help='preserve leading whitespace before a directive')
  op.add_option('--normalize-whitespace', action='store_true',
                default=False,
                help='normalize all runs of whitespace to one character')
  op.add_option('-v', '--verbose', action='store_true', default=False)
  op.add_option('-V', '--version', action='store_true', default=False)
  op.add_option('-O', dest='optimizer_level', type='int', default=0)
  op.add_option('-o', '--output-file',  dest='output_file', default=None)
  op.add_option('--xspt-mode', action='store_true', default=False,
                help='enable attribute language syntax')
  op.add_option('--x-disable-psyco', dest='x_psyco', default=True,
                action='store_false',
                help='disable psyco')
  op.add_option('--x-psyco-profile',
                action='store_true',
                help='enable psyco profiler logging')

  op.add_option('--disable-filters', dest='enable_filters',
                action='store_false', default=True)

  op.add_option('--output-directory', default='',
                action="callback", callback=validate_path,
                type="str", nargs=1,
                help='alternate directory to store compiled templates')

  op.add_option('--base-extends-package', default=None)
  op.add_option('--extract-message-catalogue', action='store_true',
                default=False)
  op.add_option('--message-catalogue-file', default=None,
                action="callback", callback=validate_path,
                type="str", nargs=1,
                help='file to use as the message catalogue')
  op.add_option('--locale', default='')
  op.add_option('--function-registry-file', default=None,
                action="callback", callback=validate_path,
                type="str", nargs=1,
                help='file to use as the function registry')
  op.add_option('-X', dest='optimizer_flags', action='append', default=[],
                help=analyzer.AnalyzerOptions.get_help())
  
