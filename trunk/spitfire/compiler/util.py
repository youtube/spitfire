import new
import os.path
import re
import sys

import spitfire.compiler.codegen
import spitfire.compiler.parser
import spitfire.compiler.scanner
import spitfire.compiler.analyzer
import spitfire.compiler.optimizer
import spitfire.compiler.xhtml2ast

from spitfire.compiler import analyzer
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

def parse_file(filename, xhtml=False):
  return parse_template(read_template_file(filename), xhtml=xhtml)

def parse_template(src_text, xhtml=False):
  if xhtml:
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


# compile a text file into a template object
# this won't recursively import templates, it's just a convenience in the case
# where you need to create a fresh object directly from raw template file
def load_template_file(filename, module_name=None,
                       options=spitfire.compiler.analyzer.default_options,
                       xhtml=False):
  c = Compiler(analyzer_options=options, xhtml_mode=xhtml)
  class_name = filename2classname(filename)
  if not module_name:
    module_name = class_name

  src_code = c.compile_file(filename)
  module = load_module_from_src(src_code, filename, module_name)
  return getattr(module, class_name)

def load_template(template_src, template_name,
                  options=spitfire.compiler.analyzer.default_options):
  class_name = filename2classname(template_name)
  filename = '<%s>' % class_name
  module_name = class_name
  c = Compiler(analyzer_options=options)
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
    'extract_message_catalogue',
    'ignore_optional_whitespace',
    'locale',
    'message_catalogue_file',
    'optimizer_level',
    'output_directory',
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
    self.xhtml_mode = False
    self.write_file = False
    self.analyzer_options = None

    self.optimizer_level = 0
    self.ignore_optional_whitespace = False

    self.base_extends_package = None
    self.message_catalogue = None
    self.message_catalogue_file = None
    self.extract_message_catalogue = False
    self.locale = None

    self.macro_registry = {}

    for key, value in kargs.iteritems():
      setattr(self, key, value)
    
    if self.analyzer_options is None:
      self.analyzer_options = analyzer.optimizer_map[self.optimizer_level]
      self.analyzer_options.ignore_optional_whitespace = self.ignore_optional_whitespace

    # register macros before the first pass by any SemanticAnalyzer
    # this is just a default to give an example - it's not totally functional
    # fixme: nasty time to import - but does break weird cycle
    import spitfire.compiler.macros.i18n
    self.register_macro('macro_i18n', spitfire.compiler.macros.i18n.macro_i18n)

  # take an AST and generate code from it - this will run the analysis phase
  # this doesn't have the same semantics as python's AST operations
  # it would be good to have a reason for the inconsistency other than
  # laziness or stupidity
  def compile_ast(self, parse_root, classname):
    ast_root = analyzer.SemanticAnalyzer(
      classname, parse_root, self.analyzer_options, self).get_ast()
    spitfire.compiler.optimizer.OptimizationAnalyzer(
      ast_root, self.analyzer_options, self).optimize_ast()
    code_generator = codegen.CodeGenerator(ast_root,
                                           self.analyzer_options)
    return code_generator.get_code()

  def compile_template(self, src_text, classname):
    return self.compile_ast(parse_template(src_text, xhtml=self.xhtml_mode),
                            classname)

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
