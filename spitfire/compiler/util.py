# Copyright 2007 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import logging
import new
import os.path
import re
import sys

from spitfire.compiler import options
from spitfire.compiler import parser
from spitfire.compiler import scanner
from spitfire import runtime

valid_identfier = re.compile('[_a-z]\w*', re.IGNORECASE)


def filename2classname(filename):
    classname = os.path.splitext(os.path.basename(filename))[0].replace('-',
                                                                        '_')
    if not valid_identfier.match(classname):
        raise SyntaxError('filename "%s" must yield valid python identifier: %s'
                          % (filename, classname))
    return classname


def filename2modulename(filename):
    names = [filename2classname(p) for p in filename.split(os.path.sep)]
    return '.'.join(names)


# @return abstract syntax tree rooted on a ast.TemplateNode
def parse(src_text, rule='goal'):
    spt_parser = parser.SpitfireParser(scanner.SpitfireScanner(src_text))
    return parser.wrap_error_reporter(spt_parser, rule)


def parse_file(filename, xspt_mode=False):
    template_node = parse_template(read_template_file(filename), xspt_mode)
    template_node.source_path = filename
    return template_node


def parse_template(src_text, xspt_mode=False):
    if xspt_mode:
        # Note: The compiler module is imported here to avoid a circular
        # dependency.
        from spitfire.compiler import xhtml2ast
        xspt_parser = xhtml2ast.XHTML2AST()
        return xspt_parser.parse(src_text)
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
    lines = f.readlines()
    f.close()
    new_format = [l for l in lines
                  if not l.startswith('#') and l.find(',') > -1]
    function_registry = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('#'):
            continue
        if new_format:
            alias, rest = line.split('=')
            decorators = rest.split(',')
            fq_name = decorators.pop(0).strip()
            function_registry[alias.strip()] = fq_name, decorators
        else:
            alias, fq_name = line.split('=')
            fq_name = fq_name.strip()
            try:
                method = runtime.import_module_symbol(fq_name)
            except ImportError:
                logging.warning('unable to import function registry symbol %s',
                                fq_name)
                method = None
            function_registry[alias.strip()] = fq_name, method
    return new_format, function_registry


# compile a text file into a template object
# this won't recursively import templates, it's just a convenience in the case
# where you need to create a fresh object directly from raw template file
def load_template_file(filename,
                       module_name=None,
                       analyzer_options=options.default_options,
                       compiler_options=None,
                       xspt_mode=False):
    # Note: The compiler module is imported here to avoid a circular dependency.
    from spitfire.compiler import compiler
    spt_compiler = compiler.Compiler(analyzer_options=analyzer_options,
                                     xspt_mode=xspt_mode)
    if compiler_options:
        for k, v in compiler_options.iteritems():
            setattr(spt_compiler, k, v)
    class_name = filename2classname(filename)
    if not module_name:
        module_name = class_name

    src_code = spt_compiler.compile_file(filename)
    module = load_module_from_src(src_code, filename, module_name)
    return getattr(module, class_name)


def load_template(template_src,
                  template_name,
                  analyzer_options=options.default_options,
                  compiler_options=None):
    class_name = filename2classname(template_name)
    filename = '<%s>' % class_name
    module_name = class_name
    # Note: The compiler module is imported here to avoid a circular dependency
    from spitfire.compiler import compiler
    spt_compiler = compiler.Compiler(analyzer_options=analyzer_options)
    if compiler_options:
        for k, v in compiler_options.iteritems():
            setattr(spt_compiler, k, v)
    src_code = spt_compiler.compile_template(template_src, class_name)
    module = load_module_from_src(src_code, filename, module_name)
    return getattr(module, class_name)


# a helper method to import a template without having to save it to disk
def load_module_from_src(src_code, filename, module_name):
    module = new.module(module_name)
    sys.modules[module_name] = module

    bytecode = compile(src_code, filename, 'exec')
    exec bytecode in module.__dict__
    return module


# convert and extends path to a file path
def extends2path(class_extend):
    return class_extend.replace('.', '/') + '.spt'
