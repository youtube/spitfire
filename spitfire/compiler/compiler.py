# Copyright 2014 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import copy
import gc
import os.path
import sys

from spitfire.compiler import analyzer
from spitfire.compiler import codegen
from spitfire.compiler import optimizer
from spitfire.compiler import options
from spitfire.compiler import util


class CompilerError(Exception):
    pass


class Warning(Exception):
    pass


class Compiler(object):
    setting_names = [
        'baked_mode',
        'base_extends_package',
        'base_template_full_import_path',
        'debug_flags',
        'compiler_stack_traces',
        'default_to_strict_resolution',
        'double_assign_error',
        'enable_filters',
        'extract_message_catalogue',
        'fail_library_searchlist_access',
        'function_registry_file',
        'ignore_optional_whitespace',
        'include_sourcemap',
        'include_path',
        'locale',
        'message_catalogue_file',
        'no_raw',
        'normalize_whitespace',
        'optimizer_flags',
        'optimizer_level',
        'output_directory',
        'skip_import_udn_resolution',
        'static_analysis',
        'strict_global_check',
        'tune_gc',
        'enable_warnings',
        'warnings_as_errors',
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
        self.src_text = None
        self.src_line_map = []
        self.output_directory = ''
        self.xspt_mode = False
        self.write_file = False
        self.analyzer_options = None
        self.include_sourcemap = False
        # This context can be used by macros to handle state when
        # compiling a file. Each macro should use its own namespace to
        # avoid conflicts. This is not enforced in any way. The context is
        # reset after compiling a single file. A simple example is
        # counting the number of times a macro has run.
        self.macro_context = {}

        self.optimizer_level = 0
        self.optimizer_flags = []
        self.debug_flags = []
        self.compiler_stack_traces = False
        self.ignore_optional_whitespace = False
        self.normalize_whitespace = False
        self.fail_library_searchlist_access = False
        self.skip_import_udn_resolution = False
        self.default_to_strict_resolution = False
        self.static_analysis = False
        self.strict_global_check = False
        self.double_assign_error = False
        self.enable_warnings = False
        self.warnings_as_errors = False
        self.baked_mode = False
        self.no_raw = False

        self.base_extends_package = None
        self.base_template_full_import_path = None
        self.message_catalogue = None
        self.message_catalogue_file = None
        self.extract_message_catalogue = False
        self.locale = None
        self.include_path = '.'
        self.enable_filters = True
        self.tune_gc = False

        # the function registry is for optimized access to 'first-class'
        # functions things that get accessed all the time that should be speedy
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
            self.analyzer_options = options.optimizer_map[self.optimizer_level]
            if self.base_template_full_import_path:
                self.analyzer_options.base_template_full_import_path = (
                    self.base_template_full_import_path)
            self.analyzer_options.ignore_optional_whitespace = (
                self.ignore_optional_whitespace)
            self.analyzer_options.normalize_whitespace = (
                self.normalize_whitespace)
            self.analyzer_options.fail_library_searchlist_access = (
                self.fail_library_searchlist_access)
            self.analyzer_options.skip_import_udn_resolution = (
                self.skip_import_udn_resolution)
            self.analyzer_options.static_analysis = self.static_analysis
            self.analyzer_options.strict_global_check = self.strict_global_check
            self.analyzer_options.double_assign_error = self.double_assign_error
            self.analyzer_options.default_to_strict_resolution = (
                self.default_to_strict_resolution)
            self.analyzer_options.include_sourcemap = self.include_sourcemap
            self.analyzer_options.baked_mode = self.baked_mode
            self.analyzer_options.no_raw = self.no_raw

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
            self.new_registry_format, self.function_name_registry = (
                util.read_function_registry(self.function_registry_file))

        # register macros before the first pass by any SemanticAnalyzer this is
        # just a default to give an example - it's not totally functional fixme:
        # nasty time to import - but does break weird cycle
        import spitfire.compiler.macros.i18n
        self.register_macro('macro_i18n',
                            spitfire.compiler.macros.i18n.macro_i18n)
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

        optimizer.OptimizationAnalyzer(
            self._optimized_tree, self.analyzer_options, self).optimize_ast()

        if self.debug_flags:
            self._hoisted_tree = copy.deepcopy(self._optimized_tree)
        else:
            self._hoisted_tree = self._optimized_tree

        optimizer.FinalPassAnalyzer(self._hoisted_tree, self.analyzer_options,
                                    self).optimize_ast()

        self._source_code = codegen.CodeGenerator(
            self._hoisted_tree, self, self.analyzer_options).get_code()
        return self._source_code

    def _reset(self):
        self._parse_tree = None
        self._analyzed_tree = None
        self._optimized_tree = None
        self._hoisted_tree = None
        self._source_code = None
        self.macro_context = {}

    def calculate_line_and_column(self, pos):
        if not self.src_text:
            return (0, 0)
        lineno = 1 + self.src_text.count('\n', 0, pos)
        colno = pos - (self.src_text.rfind('\n', 0, pos) + 2)
        return (lineno, colno)

    def print_stderr_message(self,
                             message,
                             pos=None,
                             is_error=False,
                             is_warning=False):
        if is_warning:
            # Print out WARNING in magenta.
            sys.stderr.write('\033[1;35mWARNING:\033[1;m ')
        elif is_error:
            # Print out ERROR in red.
            sys.stderr.write('\033[1;31mERROR:\033[1;m ')
        else:
            # Print out INFO in yellow.
            sys.stderr.write('\033[1;32mINFO:\033[1;m ')
        if pos is None:
            sys.stderr.write('%s ' % self.src_filename)
        else:
            lineno, colno = self.calculate_line_and_column(pos)
            sys.stderr.write('%s:%s:%s ' % (self.src_filename, lineno, colno))
        sys.stderr.write(message)
        sys.stderr.write('\n')

    def warn(self, message, pos=None):
        if not self.enable_warnings:
            return
        if self.warnings_as_errors:
            self.error(Warning(message), pos=pos)
        else:
            self.print_stderr_message(message, pos=pos, is_warning=True)

    def error(self, err, pos=None):
        if self.compiler_stack_traces:
            raise err
        else:
            self.print_stderr_message(str(err), pos=pos, is_error=True)
            sys.exit(1)

    def compile_template(self, src_text, classname):
        if self.tune_gc:
            gc.disable()
        try:
            self._reset()
            self._parse_tree = util.parse_template(src_text, self.xspt_mode)
            return self._compile_ast(self._parse_tree, classname)
        finally:
            if self.tune_gc:
                self._reset()
                gc.enable()
                gc.collect()

    def compile_file(self, filename):
        self.src_filename = filename
        self.classname = util.filename2classname(filename)
        self.src_text = util.read_template_file(filename)
        self.generate_line_map()
        src_code = self.compile_template(self.src_text, self.classname)
        if self.write_file:
            self.write_src_file(src_code)
        return src_code

    def generate_line_map(self):
        self.src_line_map = []
        current_line = 1
        for c in self.src_text:
            self.src_line_map.append(current_line)
            if c == '\n':
                current_line += 1

    def write_src_file(self, src_code):
        outfile_name = '%s.py' % self.classname
        relative_dir = os.path.dirname(self.src_filename)
        if self.output_directory and os.path.isabs(relative_dir):
            self.error(CompilerError(
                "can't mix output_directory and absolute paths"))

        outfile_path = os.path.join(self.output_directory, relative_dir,
                                    outfile_name)
        outfile = open(outfile_path, 'w')
        outfile.write(src_code)
        outfile.close()

    def registry_contains(self, fname):
        """Returns True if the registry contains a function."""
        return fname in self.function_name_registry

    def get_registry_value(self, fname, key):
        """Get the value associated with a key in the function registry
        for a function. The function returns None, if the function is not
        found in the registry.

        This function assumes that all registry entries are booleans.
        """
        if self.registry_contains(fname):
            decorators = self.function_name_registry[fname][-1]
            if self.new_registry_format:
                return key in decorators
            else:
                return getattr(decorators, key, False)
        return None

    # macros could be handy - and they are complex enough that they should be
    # put somewhere else. this registry allows them to be implemented just about
    # anywhere.
    #
    # macro functions look like: def macro_handler(macro_node, arg_map)
    # arg_map is a dictionary of names to values specified as parameters to the
    # macro by the template source, limited to literal values right now.
    #
    # The parse_rule argument should be string that is the name of the
    # rule you wish to parse. These rules are defined in parser.g.
    def register_macro(self, name, function, parse_rule=None):
        self.macro_registry[name] = (function, parse_rule)
