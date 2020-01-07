# Copyright 2014 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import copy
import os


class AnalyzerOptions(object):

    DEFAULT_BASE_TEMPLATE_FULL_IMPORT_PATH = (
        'spitfire.runtime.template.SpitfireTemplate')

    def __init__(self, **kargs):
        self.debug = False

        self.ignore_optional_whitespace = False

        # adjacent text nodes become one single node
        self.collapse_adjacent_text = False

        # generate templates with unicode() instead of str()
        self.generate_unicode = True

        # runs of whitespace characters are replace with one space
        self.normalize_whitespace = False

        # expensive dotted notations are aliased to a local variable for faster
        # lookups: write = self.buffer.write
        self.alias_invariants = False

        # when a variable defined in a block later is accessed, just use the raw
        # identifier, don't incure the cost of a resolve_placeholder call since
        # you know that this local variable will always resolve first
        self.directly_access_defined_variables = False

        # examine the 'extends' directive to see what other methods will be
        # defined on this template - that allows use to make fast calls to
        # template methods outside of the immediate file.
        self.use_dependency_analysis = False

        # if directly_access_defined_variables is working 100% correctly, you
        # can compleletely ignore the local scope, as those placeholders will
        # have been resolved at compile time. there are some complex cases where
        # there are some problems, so it is disabled for now
        self.omit_local_scope_search = False

        # once a placeholder is resolved in a given scope, cache it in a local
        # reference for faster subsequent retrieval
        self.cache_resolved_placeholders = False
        self.cache_resolved_udn_expressions = False
        # when this is enabled, $a.b.c will cache only the result of the entire
        # expression. otherwise, each subexpression will be cached separately
        self.prefer_whole_udn_expressions = False

        # Throw an exception when a udn resolution fails rather than providing a
        # default value
        self.raise_udn_exceptions = False

        # when adding an alias, detect if the alias is loop invariant and hoist
        # right there on the spot.  this has probably been superceded by
        # hoist_loop_invariant_aliases, but does have the advantage of not
        # needing another pass over the tree
        self.inline_hoist_loop_invariant_aliases = False

        # if an alias has been generated in a conditional scope and it is also
        # defined in the parent scope, hoist it above the conditional. this
        # requires a two-pass optimization on functions, which adds time and
        # complexity
        self.hoist_conditional_aliases = False
        self.hoist_loop_invariant_aliases = False

        # filtering is expensive, especially given the number of function calls
        self.cache_filtered_placeholders = False

        # generate functions compatible with Cheetah calling conventions
        self.cheetah_compatibility = False
        # use Cheetah NameMapper to resolve placeholders and UDN
        self.cheetah_cheats = False

        # the nested def doesn't make sense - unlike block, so raise an error.
        # default off for now to let people ease into it.
        self.fail_nested_defs = False

        # whether to explode on library search list accesses that are not
        # declared with #global $foo beforehand
        self.fail_library_searchlist_access = False

        # If we can skip udn resolution and instead directly access modules
        # imported via #import and #from directives.
        self.skip_import_udn_resolution = False

        # By default Spitfire will jump through hoops to resolve dot notation.
        # This flag disables this resolution and instead uses direct python
        # access. If this flag can be overriden on a per-file basis by using the
        # "#loose_resolution" directive.
        self.default_to_strict_resolution = False

        # Fully qualified import path of the base Spitfire template class.
        self.base_template_full_import_path = (
            self.DEFAULT_BASE_TEMPLATE_FULL_IMPORT_PATH)

        # Batch buffer writes as buffer.extend operations. This moves the
        # buffer operations to the end of a scope.
        self.batch_buffer_writes = False

        # Spitfire templates do not allow for the use of |raw.
        self.baked_mode = False

        # Throw compiler errors if variables are used outside of their scope.
        self.static_analysis = False

        # Disallow the use of raw in a template.
        self.no_raw = False

        # Generate line number comments in compiler output.
        self.include_sourcemap = False

        self.__dict__.update(kargs)

    def update(self, **kargs):
        self.__dict__.update(kargs)

    @classmethod
    def get_help(cls):
        return ', '.join(['[no-]' + name.replace('_', '-')
                          for name, value in vars(cls()).items()
                          if not name.startswith('__') and type(value) == bool])


default_options = AnalyzerOptions()
o1_options = copy.copy(default_options)
o1_options.collapse_adjacent_text = True

o2_options = copy.copy(o1_options)
o2_options.alias_invariants = True
o2_options.directly_access_defined_variables = True
o2_options.cache_resolved_placeholders = True
o2_options.cache_resolved_udn_expressions = True
o2_options.inline_hoist_loop_invariant_aliases = True
o2_options.use_dependency_analysis = True

o3_options = copy.copy(o2_options)
o3_options.inline_hoist_loop_invariant_aliases = False
o3_options.hoist_conditional_aliases = True
o3_options.hoist_loop_invariant_aliases = True
o3_options.cache_filtered_placeholders = True
o3_options.omit_local_scope_search = True
o3_options.batch_buffer_writes = True

optimizer_map = {
    0: default_options,
    1: o1_options,
    2: o2_options,
    3: o3_options,
}


# standard options to any compiler front-end
# @op option_parser, this object will be modified
def add_common_options(op):
    op.add_option('--preserve-optional-whitespace',
                  action='store_false',
                  default=True,
                  dest='ignore_optional_whitespace',
                  help='preserve leading whitespace before a directive')
    op.add_option('--normalize-whitespace',
                  action='store_true',
                  default=False,
                  help='normalize all runs of whitespace to one character')
    op.add_option(
        '--fail-library-searchlist-access',
        action='store_true',
        default=False,
        help='disallow searchlist accesses inside template libraries not '
        'declared with #global')
    op.add_option('--skip-import-udn-resolution',
                  action='store_true',
                  default=False,
                  help='Skip UDN resolution for imported moudles')
    op.add_option(
        '--strict-global-check',
        action='store_true',
        default=False,
        help='Throw compiler errors if display vars or extended methods'
        ' are not declared #global. Overridden by #loose_resolution')
    op.add_option('--static-analysis',
                  action='store_true',
                  default=False,
                  help='Throw compiler errors if variables are used outside '
                  'of their scope.')
    op.add_option(
        '--default-to-strict-resolution',
        action='store_true',
        default=False,
        help='Resolve dotted values in python instead of using resolve_UDN')
    op.add_option('-v', '--verbose', action='store_true', default=False)
    op.add_option('-V', '--version', action='store_true', default=False)
    op.add_option('-O', dest='optimizer_level', type='int', default=0)
    op.add_option('-o', '--output-file', dest='output_file', default=None)
    op.add_option('--xspt-mode',
                  action='store_true',
                  default=False,
                  help='enable attribute language syntax')

    op.add_option('--disable-filters',
                  dest='enable_filters',
                  action='store_false',
                  default=True)

    op.add_option('--output-directory',
                  default='',
                  action='callback',
                  callback=validate_path,
                  type='str',
                  nargs=1,
                  help='alternate directory to store compiled templates')

    op.add_option(
        '--include-path',
        default='.',
        action='callback',
        callback=validate_path,
        type='str',
        nargs=1,
        help='path to the templates hierarchy, where included files live. '
        'default: .')

    op.add_option('--base-extends-package', default=None)
    op.add_option('--extract-message-catalogue',
                  action='store_true',
                  default=False)
    op.add_option('--message-catalogue-file',
                  default=None,
                  action='callback',
                  callback=validate_path,
                  type='str',
                  nargs=1,
                  help='file to use as the message catalogue')
    op.add_option('--locale', default='')
    op.add_option('--function-registry-file',
                  default=None,
                  action='callback',
                  callback=validate_path,
                  type='str',
                  nargs=1,
                  help='file to use as the function registry')
    op.add_option('-X',
                  dest='optimizer_flags',
                  action='append',
                  default=[],
                  help=AnalyzerOptions.get_help())
    op.add_option('--tune-gc', action='store_true')
    op.add_option('--Wall',
                  action='store_true',
                  default=False,
                  dest='enable_warnings',
                  help='Show all warnings.')
    op.add_option('--Werror',
                  action='store_true',
                  default=False,
                  dest='warnings_as_errors',
                  help='Treat all warnings as errors')
    op.add_option('--compiler-stack-traces',
                  default=False,
                  action='store_true',
                  help='Get stack traces on compiler errors')
    op.add_option('--include-sourcemap',
                  default=False,
                  action='store_true',
                  help='Annotate output with sourcemap like comments.')
    op.add_option(
        '--double-assign-error',
        default=False,
        action='store_true',
        help='Throw an error if there is an unsafe double assignment.')
    op.add_option('--baked-mode',
                  default=False,
                  action='store_true',
                  help='A mode where the runtime tracks sanitization.')
    op.add_option(
        '--no-raw',
        default=False,
        action='store_true',
        help='A stricter version of spitfire where |raw is prohibited.')
    op.add_option('--base-template-full-import-path',
                  action='store',
                  type='string',
                  help='Sets the import path of the base abstract template.')


def validate_path(option, opt_str, path, parser):
    path = os.path.abspath(os.path.expanduser(path))
    setattr(parser.values, option.dest, path)
