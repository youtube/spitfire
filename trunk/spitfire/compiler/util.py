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

def write_src_file(src_code, filename):
  classname = filename2classname(filename)
  outfile_name = '%s.py' % classname
  outfile_path = os.path.join(os.path.dirname(filename), outfile_name)
  outfile = open(outfile_path, 'w')
  outfile.write(src_code)
  outfile.close()


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


__macro_registry_inited = False
# register some default macros
def register_macros():
  global __macro_registry_inited
  if __macro_registry_inited:
    return
    
  import spitfire.compiler.macros.i18n
  spitfire.compiler.analyzer.register_macro(
    'macro_i18n',
    spitfire.compiler.macros.i18n.macro_i18n)

  __macro_registry_inited = True

class CompilerSettings(object):
  setting_names = ['optimizer_level', 'ignore_optional_whitespace']
  optimizer_level = 0
  ignore_optional_whitespace = False

  @classmethod
  def settings_from_optparse(cls, options):
    settings = CompilerSettings()
    for name in cls.setting_names:
      if hasattr(options, name):
        setattr(settings, name, getattr(options, name))
    return settings

class Compiler(object):
  # settings - arbitrary dictionary of values, probably from the command line
  def __init__(self, settings=None, **kargs):
    # record transient state of the compiler
    self.src_filename = None
    self.xhtml_mode = False
    self.settings = settings
    self.write_file = False
    self.analyzer_options = None
    if self.settings is not None:
      self.analyzer_options = analyzer.optimizer_map[settings.optimizer_level]
      self.analyzer_options.ignore_optional_whitespace = settings.ignore_optional_whitespace
    for key, value in kargs.iteritems():
      setattr(self, key, value)
    # register macros before the first pass by any SemanticAnalyzer
    register_macros()
    
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
    src_text = read_template_file(filename)
    src_code = self.compile_template(src_text, filename2classname(filename))
    if self.write_file:
      write_src_file(src_code, filename)
    return src_code
