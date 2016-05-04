# Copyright 2007 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import copy
import os.path

from spitfire.compiler import ast
from spitfire.compiler import util
from spitfire import text


def tree_walker(node):
    yield node
    for n in node.child_nodes:
        for ng in tree_walker(n):
            yield ng


class SemanticAnalyzerError(Exception):
    pass


class MacroError(SemanticAnalyzerError):
    pass


class MacroParseError(MacroError):
    pass


i18n_function_name = 'i18n'

# This is a whitelist of nodes that are allowed at the top level in
# template libraries.
# TODO: Remove ast.TextNode once b/15314057 is fixed.
_ALLOWED_LIBRARY_NODES = (ast.TextNode, ast.ImplementsNode, ast.ImportNode,
                          ast.WhitespaceNode, ast.LooseResolutionNode,
                          ast.AllowUndeclaredGlobalsNode, ast.CommentNode,
                          ast.DefNode, ast.GlobalNode)

# This is a list of nodes that cannot exclusively make up the body of
# an if or for block.
_BLANK_NODES = (ast.WhitespaceNode, ast.CommentNode)

# convert the parse tree into something a bit more 'fat' and useful
# is this an AST? i'm not sure. it will be a tree of some sort
# this should simplify the codegen stage into a naive traversal
# even though this uses memory, i'll make a copy instead of decorating the
# original tree so i can compare the differences
# the other idea is that i can treat certain nodes as 'macros' to generate a
# few nodes that are more python-like
# additionally, there are some optimizations that are really more oriented at
# the parse tree, so i do them inline here. it's a bit split-brain, but it's
# seems easier.


class SemanticAnalyzer(object):

    def __init__(self, classname, parse_root, options, compiler):
        self.classname = classname
        self.parse_root = parse_root
        self.options = options
        self.compiler = compiler
        self.ast_root = None
        self.template = None
        self.strip_lines = False
        self.uses_raw = False
        self.base_extends_identifiers = []
        if self.compiler.base_extends_package:
            # this means that extends are supposed to all happen relative to
            # some other package - this is handy for assuring all templates
            # reference within a tree, say for localization, where each locale
            # might have its own package
            packages = self.compiler.base_extends_package.split('.')
            self.base_extends_identifiers = [
                ast.IdentifierNode(module_name) for module_name in packages
            ]

    def get_ast(self):
        ast_node_list = self.build_ast(self.parse_root)
        if len(ast_node_list) != 1:
            self.compiler.error(SemanticAnalyzerError(
                'ast must have 1 root node'))
        self.ast_root = ast_node_list[0]
        return self.ast_root

    # build an AST node list from a single parse node
    # need the parent in case we are going to delete a node
    def build_ast(self, node):
        method_name = 'analyze%s' % node.__class__.__name__
        method = getattr(self, method_name, self.default_analyze_node)
        # print method_name, node.name, node
        ast_node_list = method(node)
        try:
            if len(ast_node_list) != 1:
                return ast_node_list
        except TypeError, e:
            self.compiler.error(SemanticAnalyzerError('method: %s, result: %s' %
                                                      (method, ast_node_list)))

        # print '<', ast_node_list[0].name, ast_node_list[0]
        return ast_node_list

    def default_analyze_node(self, pnode):
        # print "default_analyze_node", type(pnode)
        return [pnode]

    # some nodes just don't need analysis
    def skip_analyze_node(self, pnode):
        return [pnode]

    analyzeIdentifierNode = skip_analyze_node
    analyzeLiteralNode = skip_analyze_node

    def analyzeTemplateNode(self, pnode):
        self.template = pnode.copy(copy_children=False)
        self.template.classname = self.classname
        # Baked mode and generate_unicode are incomaptible. This is a
        # result of SanitizedPlaceholder extending str and not unicode. A
        # possible solution is to have two classes:
        # SanitizedPlaceholderUnicode and SanitizedPlaceholderStr, each
        # that extends unicode or str. Depending on the mode, it would
        # assign SanitizedPlaceholder to be the correct class.
        if self.options.generate_unicode and self.options.baked_mode:
            self.compiler.error(
                SemanticAnalyzerError(
                    'Generate unicode is incompatible with baked mode.'),
                pos=pnode.pos)
        self.template.baked = self.options.baked_mode

        # Need to build a full list of template_methods before analyzing so we
        # can modify CallFunctionNodes as we walk the tree below.
        for child_node in tree_walker(pnode):
            if (isinstance(child_node, ast.DefNode) and
                    not isinstance(child_node, ast.MacroNode)):
                if child_node.name in self.template.template_methods:
                    self.compiler.error(
                        SemanticAnalyzerError(
                            'Redefining #def/#block %s (duplicate def in file?)'
                            % (child_node.name)),
                        pos=pnode.pos)
                self.template.template_methods.add(child_node.name)

        for pn in self.optimize_parsed_nodes(pnode.child_nodes):
            if self.template.library and not isinstance(pn,
                                                        _ALLOWED_LIBRARY_NODES):
                self.compiler.error(
                    SemanticAnalyzerError(
                        'All library code must be in a function.'),
                    pos=pn.pos)
            built_nodes = self.build_ast(pn)
            if built_nodes and not self.template.library:
                self.template.main_function.extend(built_nodes)

        if not self.uses_raw and self.template.explicitly_allow_raw:
            self.compiler.error(SemanticAnalyzerError(
                '#allow_raw directive is not needed'))

        self.template.main_function.child_nodes = self.optimize_buffer_writes(
            self.template.main_function.child_nodes)

        if self.template.extends_nodes and self.template.library:
            self.compiler.error(SemanticAnalyzerError(
                "library template can't have extends."))

        return [self.template]

    # Recursively grabs identifiers from a ast.TargetListNode, such as in a
    # ast.ForNode.
    def _getIdentifiersFromListNode(self, identifier_set, target_list_node):
        for pn in target_list_node.child_nodes:
            if isinstance(pn, ast.TargetNode):
                identifier_set.add(pn.name)
            elif isinstance(pn, ast.TargetListNode):
                self._getIdentifiersFromListNode(identifier_set, pn)

    def analyzeForNode(self, pnode):
        # If all of the children are nodes that get ignored or there are
        # no nodes, throw an error.
        if all([isinstance(pn, _BLANK_NODES) for pn in pnode.child_nodes]):
            self.compiler.error(
                SemanticAnalyzerError("can't define an empty #for loop"),
                pos=pnode.pos)

        for_node = ast.ForNode(pos=pnode.pos)

        # Backup original scope identifiers for analysis.
        template_local_scope_identifiers = set(
            self.template.local_scope_identifiers)

        self._getIdentifiersFromListNode(self.template.local_scope_identifiers,
                                         pnode.target_list)

        for pn in pnode.target_list.child_nodes:
            for_node.target_list.extend(self.build_ast(pn))
        for pn in pnode.expression_list.child_nodes:
            for_node.expression_list.extend(self.build_ast(pn))
        for pn in self.optimize_parsed_nodes(pnode.child_nodes):
            for_node.extend(self.build_ast(pn))

        for_node.child_nodes = self.optimize_buffer_writes(for_node.child_nodes)

        # Restore original scope identifiers after children have been analyzed.
        self.template.local_scope_identifiers = template_local_scope_identifiers

        return [for_node]

    def analyzeStripLinesNode(self, pnode):
        if self.strip_lines:
            self.compiler.error(
                SemanticAnalyzerError("can't nest #strip_lines"),
                pos=pnode.pos)
        self.strip_lines = True
        optimized_nodes = self.optimize_parsed_nodes(pnode.child_nodes)
        new_nodes = [self.build_ast(pn) for pn in optimized_nodes]
        self.strip_lines = False
        return self.optimize_buffer_writes(new_nodes)

    def analyzeGetUDNNode(self, pnode):
        children = pnode.getChildNodes()
        if isinstance(children[0], ast.PlaceholderNode):
            identifier = '.'.join([node.name for node in children])
            # Some modules are trusted not to need UDN resolution.
            if self._identifier_can_skip_UDN_resolution(identifier):
                expr = '%s.%s' % (identifier, pnode.name)
                return [ast.IdentifierNode(expr, pos=pnode.pos)]

        expression = self.build_ast(pnode.expression)[0]
        return [ast.GetUDNNode(expression, pnode.name, pos=pnode.pos)]

    def analyzeGetAttrNode(self, pnode):
        expression = self.build_ast(pnode.expression)[0]
        return [ast.GetAttrNode(expression, pnode.name, pos=pnode.pos)]

    def analyzeIfNode(self, pnode):
        # If all of the children are nodes that get ignored or there are
        # no nodes, throw an error.
        if all([isinstance(pn, _BLANK_NODES) for pn in pnode.child_nodes]):
            self.compiler.error(
                SemanticAnalyzerError("can't define an empty #if block"),
                pos=pnode.pos)

        if_node = ast.IfNode(pos=pnode.pos)
        if_node.else_.pos = pnode.else_.pos
        if_node.test_expression = self.build_ast(pnode.test_expression)[0]
        for pn in self.optimize_parsed_nodes(pnode.child_nodes):
            if_node.extend(self.build_ast(pn))
            if_node.child_nodes = self.optimize_buffer_writes(
                if_node.child_nodes)
        for pn in self.optimize_parsed_nodes(pnode.else_.child_nodes):
            if_node.else_.extend(self.build_ast(pn))
            if_node.else_.child_nodes = self.optimize_buffer_writes(
                if_node.else_.child_nodes)
        return [if_node]

    def analyzeFragmentNode(self, node):
        new_nodes = []
        for n in node.child_nodes:
            new_nodes.extend(self.build_ast(n))
        return new_nodes

    def analyzeArgListNode(self, pnode):
        list_node = ast.ArgListNode(pos=pnode.pos)
        for n in pnode:
            list_node.extend(self.build_ast(n))
        return [list_node]

    def analyzeTupleLiteralNode(self, pnode):
        tuple_node = ast.TupleLiteralNode(pos=pnode.pos)
        for n in pnode.child_nodes:
            tuple_node.extend(self.build_ast(n))
        return [tuple_node]

    def analyzeDictLiteralNode(self, pnode):
        dict_node = ast.DictLiteralNode(pos=pnode.pos)
        for key_node, value_node in pnode.child_nodes:
            key_value = (key_node, self.build_ast(value_node)[0])
            dict_node.child_nodes.extend([key_value])
        return [dict_node]

    def analyzeParameterNode(self, pnode):
        param = pnode
        param.default = self.build_ast(pnode.default)[0]
        return [param]

    def analyzeSliceNode(self, pnode):
        snode = pnode
        snode.expression = self.build_ast(pnode.expression)[0]
        snode.slice_expression = self.build_ast(pnode.slice_expression)[0]
        return [snode]

    # FIXME: should I move this to a directive?
    def analyzeImplementsNode(self, pnode):
        if pnode.name == 'library':
            self.template.library = True
        else:
            self.template.main_function.name = pnode.name
            self.template.implements = True
        return []

    def analyzeAllowUndeclaredGlobalsNode(self, pnode):
        self.template.allow_undeclared_globals = True
        return []

    def analyzeLooseResolutionNode(self, pnode):
        self.template.use_loose_resolution = True
        return []

    def analyzeAllowRawNode(self, pnode):
        self.template.explicitly_allow_raw = True
        return []

    def analyzeImportNode(self, pnode):
        node = ast.ImportNode(
            [self.build_ast(n)[0] for n in pnode.module_name_list],
            library=pnode.library,
            pos=pnode.pos)
        if node.library:
            self.template.library_identifiers.add('.'.join(
                node.name for node in node.module_name_list))
            node.module_name_list[0:0] = self.base_extends_identifiers

        if node not in self.template.import_nodes:
            self.template.import_nodes.append(node)
            # Modules imported via "from" are trusted to not need UDN
            # resolution.
            self.template.trusted_module_identifiers.add('.'.join(
                node.name for node in node.module_name_list))
        return []

    def analyzeExtendsNode(self, pnode):
        # an extends directive results in two fairly separate things happening
        # clone these nodes so we can modify the path struction without mangling
        # anything else
        import_node = ast.ImportNode(pnode.module_name_list[:])
        extends_node = ast.ExtendsNode(pnode.module_name_list[:])
        if type(pnode) != ast.AbsoluteExtendsNode:
            import_node.module_name_list[0:0] = self.base_extends_identifiers
            extends_node.module_name_list[0:0] = self.base_extends_identifiers

        self.analyzeImportNode(import_node)

        # actually want to reference the class within the module name
        # assume we follow the convention of module name == class name
        extends_node.module_name_list.append(extends_node.module_name_list[-1])
        self.template.extends_nodes.append(extends_node)
        return []

    analyzeAbsoluteExtendsNode = analyzeExtendsNode

    def analyzeFromNode(self, pnode):
        if pnode.library:
            self.template.library_identifiers.add(pnode.identifier.name)
            pnode.module_name_list[0:0] = self.base_extends_identifiers
        if pnode not in self.template.from_nodes:
            self.template.from_nodes.append(pnode)
            # Modules imported via "from" are trusted to not need UDN
            # resolution.
            self.template.trusted_module_identifiers.add(pnode.identifier.name)
        return []

    def analyzeTextNode(self, pnode):
        if pnode.child_nodes:
            self.compiler.error(
                SemanticAnalyzerError("ast.TextNode can't have children"),
                pos=pnode.pos)

        value = pnode.value
        if self.options.normalize_whitespace:
            value = text.normalize_whitespace(value)
        literal_node = ast.LiteralNode(value, pos=pnode.pos)
        buffer_write = ast.BufferWrite(literal_node, pos=pnode.pos)
        return [buffer_write]

    analyzeOptionalWhitespaceNode = analyzeTextNode
    analyzeWhitespaceNode = analyzeTextNode
    analyzeNewlineNode = analyzeTextNode

    # purely here for passthru and to remind me that it needs to be overridden
    def analyzeFunctionNode(self, pnode):
        return [pnode]

    def analyzeDefNode(self, pnode, allow_nesting=False):
        if (self.options.fail_nested_defs and not allow_nesting and
                not isinstance(pnode.parent, ast.TemplateNode)):
            self.compiler.error(
                SemanticAnalyzerError('nested #def directives are not allowed'),
                pos=pnode.pos)

        function = ast.FunctionNode(pnode.name, pos=pnode.pos)
        # Backup original scope identifiers for analysis.
        template_local_scope_identifiers = set(
            self.template.local_scope_identifiers)

        if pnode.parameter_list:
            # Add parameters to local template scope for static analysis in
            # children.
            self.template.local_scope_identifiers = (
                self.template.local_scope_identifiers.union(
                    [parameter.name for parameter in pnode.parameter_list]))
            function.parameter_list = self.build_ast(pnode.parameter_list)[0]

        function.parameter_list.child_nodes.insert(
            0,
            ast.ParameterNode(name='self'))

        for pn in self.optimize_parsed_nodes(pnode.child_nodes):
            function.extend(self.build_ast(pn))
        function = self.build_ast(function)[0]
        function.child_nodes = self.optimize_buffer_writes(function.child_nodes)
        self.template.append(function)

        # Restore original scope identifiers after children have been analyzed.
        self.template.local_scope_identifiers = template_local_scope_identifiers
        return []

    def analyzeBlockNode(self, pnode):
        self.analyzeDefNode(pnode, allow_nesting=True)
        function_node = ast.CallFunctionNode(pos=pnode.pos)
        function_node.expression = self.build_ast(ast.PlaceholderNode(
            pnode.name))[0]
        p = ast.PlaceholderSubstitutionNode(function_node, pos=pnode.pos)
        call_block = self.build_ast(p)
        return call_block

    def handleMacro(self, pnode, macro_function, parse_rule):
        if isinstance(pnode, ast.MacroNode):
            kargs_map = pnode.parameter_list.get_arg_map()
        elif isinstance(pnode, ast.CallFunctionNode):
            kargs_map = pnode.arg_list.get_arg_map()
        else:
            self.compiler.error(
                SemanticAnalyzerError("unexpected node type '%s' for macro" %
                                      type(pnode)),
                pos=pnode.pos)

        macro_output = macro_function(pnode, kargs_map, self.compiler)
        # fixme: bad place to import, difficult to put at the top due to
        # cyclic dependency
        try:
            if parse_rule:
                fragment_ast = util.parse(macro_output, parse_rule)
            elif isinstance(pnode, ast.MacroNode):
                fragment_ast = util.parse(macro_output, 'fragment_goal')
            elif isinstance(pnode, ast.CallFunctionNode):
                fragment_ast = util.parse(macro_output, 'rhs_expression')
        except Exception, e:
            self.compiler.error(MacroParseError(e), pos=pnode.pos)
        return self.build_ast(fragment_ast)

    def analyzeMacroNode(self, pnode):
        # fixme: better error handler
        macro_handler_name = 'macro_%s' % pnode.name
        try:
            macro_function, macro_parse_rule = self.compiler.macro_registry[
                macro_handler_name]
        except KeyError:
            self.compiler.error(
                SemanticAnalyzerError("no handler registered for '%s'" %
                                      macro_handler_name),
                pos=pnode.pos)
        try:
            temp_fragment = util.parse(pnode.value, macro_parse_rule or
                                       'fragment_goal')
        except Exception, e:
            self.compiler.error(MacroParseError(e), pos=pnode.pos)

        if not self.uses_raw:
            for child_node in tree_walker(temp_fragment):
                if (isinstance(child_node, ast.PlaceholderSubstitutionNode) and
                        'raw' in child_node.parameter_list.get_arg_map()):
                    self.uses_raw = True
                    break

        return self.handleMacro(pnode, macro_function, macro_parse_rule)

    def analyzeGlobalNode(self, pnode):
        if not isinstance(pnode.parent, ast.TemplateNode):
            self.compiler.error(
                SemanticAnalyzerError('#global must be a top-level directive.'),
                pos=pnode.pos)
        self.template.global_placeholders.add(pnode.name)
        return []

    def analyzeAttributeNode(self, pnode):
        self.template.attr_nodes.append(pnode)
        return []

    analyzeFilterAttributeNode = analyzeAttributeNode

    # note: we do a copy-thru to force analysis of the child nodes
    # this function is drastically complicated by the logic for filtering
    # basically, if you are pulling data from the search_list and writing it
    # to the output buffer, you want to do some filtering in most cases - at
    # least when you are doing web stuff.
    # there are some cases where you want to disable this to prevent double
    # escaping or to increase performance by avoiding unnecessay work.
    #
    # $test_str_function($test_dict)
    #
    # self.resolve_placeholder('test_str_function', local_vars=locals(),
    #   global_vars=_globals)(self.resolve_placeholder('test_dict',
    #   local_vars=locals(), global_vars=_globals))
    #
    # if this section is referenced inside another template-defined function the
    # data returned should not be double escaped. you can do this by forcing all
    # template functions to annotate themselves, but you have to do more
    # cumbersome checks when you are calling arbitrary functions.
    #
    # it might be reasonable to put in another node type that indicates a block
    # of data needs to be filtered.
    def analyzePlaceholderSubstitutionNode(self, pnode):
        # print ' '.join(analyzePlaceholderSubstitutionNode', pnode,
        #                pnode.parameter_list.get_arg_map())
        node_list = []
        ph_expression = self.build_ast(pnode.expression)[0]
        # If the expression contained a macro that was parsed as a
        # fragment, the expression is now a statement and can be moved
        # outside of the ast.PlaceholderSubstitutionNode.
        #
        # This is a hack to get around design decisions that were made
        # early on. It is up to the macro authors to correctly decide how
        # the macro should be parsed and the compiler should throw errors
        # if there is an odd state where nodes are somewhere unexpected.
        if isinstance(ph_expression, ast.statement_nodes):
            return [ph_expression]

        arg_map = pnode.parameter_list.get_arg_map()
        default_format_string = '%s'
        format_string = arg_map.get('format_string', default_format_string)

        skip_filter = False
        cache_forever = False
        registered_function = False
        function_has_only_literal_args = False
        never_cache = False
        if isinstance(ph_expression, ast.CallFunctionNode):
            fname = ph_expression.expression.name
            if self.compiler.registry_contains(fname):
                function_has_only_literal_args = (
                    ph_expression.arg_list and
                    not [_arg
                         for _arg in ph_expression.arg_list
                         if not isinstance(_arg, ast.LiteralNode)])
                skip_filter = self.compiler.get_registry_value(fname,
                                                               'skip_filter')
                skip_unless_baked = self.compiler.get_registry_value(
                    fname, 'skip_filter_unless_baked')
                skip_filter = skip_filter or (not self.template.baked and
                                              skip_unless_baked)
                cache_forever = self.compiler.get_registry_value(
                    fname, 'cache_forever')
                never_cache = self.compiler.get_registry_value(fname,
                                                               'never_cache')

            elif ph_expression.library_function:
                # Don't escape function calls into library templates.
                skip_filter = True

        if (self.compiler.enable_filters and
                format_string == default_format_string and
                not isinstance(ph_expression, ast.LiteralNode)):
            arg_node_map = pnode.parameter_list.get_arg_node_map()
            if 'raw' in arg_map:
                # If this is a |raw usage and the template does not allow raw,
                # raise an error.
                self.uses_raw = True
                if (self.options.no_raw and
                        not self.template.explicitly_allow_raw):
                    err_msg = ('|raw is not allowed in templates compiled '
                               'with the --no-raw flag.')
                    self.compiler.error(
                        SemanticAnalyzerError(err_msg),
                        pos=pnode.pos)
            else:
                # if we need to filter, wrap up the node and wait for further
                # analysis later on
                if skip_filter:
                    # explicitly set the filter to none here - this means we
                    # will cache expensive pseudo-filtered nodes
                    ph_expression = ast.FilterNode(ph_expression,
                                                   None,
                                                   pos=pnode.pos)
                else:
                    ph_expression = ast.FilterNode(
                        ph_expression,
                        arg_node_map.get('filter', ast.DefaultFilterFunction),
                        pos=pnode.pos)

                # if this is a literal node, we still might want to filter it
                # but the output should always be the same - so do it once and
                # cache FIXME: could fold this and apply the function at
                # compile-time
                if (not never_cache and
                    (registered_function and function_has_only_literal_args) or
                        cache_forever or 'cache' in arg_map):
                    cache_expression = ast.CacheNode(ph_expression,
                                                     pos=pnode.pos)
                    self.template.cached_identifiers.add(cache_expression)
                    node_list.append(cache_expression)
                    ph_expression = ast.IdentifierNode(cache_expression.name,
                                                       pos=pnode.pos)

        if isinstance(ph_expression, ast.LiteralNode):
            buffer_write = ast.BufferWrite(ph_expression, pos=pnode.pos)
            node_list.append(buffer_write)
        elif (self.compiler.enable_filters and
              format_string == default_format_string):
            # we are already filtering, don't bother creating a new string
            buffer_write = ast.BufferWrite(ph_expression, pos=pnode.pos)
            node_list.append(buffer_write)
        else:
            buffer_write = ast.BufferWrite(
                ast.BinOpNode('%',
                              ast.LiteralNode(format_string,
                                              pos=pnode.pos),
                              ph_expression),
                pos=pnode.pos)
            node_list.append(buffer_write)
        return node_list

    def analyzePlaceholderNode(self, pnode):
        if (self.options.fail_library_searchlist_access and
                pnode.name not in self.template.global_placeholders):
            if (self.options.strict_global_check and
                    not self.template.allow_undeclared_globals and
                (not self.template.has_identifier(pnode.name) and
                 pnode.name not in self.compiler.function_name_registry)):
                # Break compile if no #loose_resolution and variable is not
                # available in any reasonable scope.
                err_msg = ('identifier %s is unavailable and is not declared '
                           'as a #global display variable' % pnode.name)
                self.compiler.error(
                    SemanticAnalyzerError(err_msg),
                    pos=pnode.pos)
            elif self.template.library:
                # Only do placeholder resolutions for placeholders declared with
                # #global in library templates.
                identifier_node = ast.IdentifierNode(pnode.name, pos=pnode.pos)
                return [identifier_node]
        return [pnode]

    analyzeEchoNode = analyzePlaceholderNode

    def analyzeBinOpNode(self, pnode):
        n = pnode
        n.left = self.build_ast(n.left)[0]
        n.right = self.build_ast(n.right)[0]
        return [n]

    analyzeBinOpExpressionNode = analyzeBinOpNode

    def analyzeAssignNode(self, pnode):
        # Add to template's scope, which will be removed after stepping out of
        # a ast.DefNode or ast.ForNode.
        # If the left side is a ast.SliceNode, make sure the expression is an
        # ast.IdentifierNode and add the expression's name.
        if isinstance(pnode.left, ast.SliceNode):
            exp = pnode.left.expression
            if not isinstance(exp, ast.IdentifierNode):
                self.compiler.error(
                    SemanticAnalyzerError(
                        'Slice expression %s in an assign must be an identifier'
                        % exp),
                    pos=pnode.pos)
        else:
            self.template.local_scope_identifiers.add(pnode.left.name)
        return self.analyzeBinOpNode(pnode)

    def analyzeUnaryOpNode(self, pnode):
        n = pnode
        n.expression = self.build_ast(n.expression)[0]
        return [n]

    def analyzeCommentNode(self, pnode):
        return []

    def analyzeDoNode(self, pnode):
        n = pnode
        n.expression = self.build_ast(n.expression)[0]
        return [n]

    def analyzeCallFunctionNode(self, pnode):
        fn = pnode

        fname = fn.expression.name
        if self.compiler.registry_contains(fname):
            # If this is a placeholder that is in the function registry, mark it
            # as used so that in the optimizer stage, we can avoid importing
            # unused registry values.
            self.template.used_function_registry_identifiers.add(fname)

        # The fully qualified library function name iff we figure out
        # that this is calling into a library.
        library_function = None
        skip_filter = self.compiler.get_registry_value(fname,
                                                       'skip_filter')

        if isinstance(fn.expression, ast.PlaceholderNode):
            macro_handler_name = 'macro_function_%s' % fn.expression.name
            macro_data = self.compiler.macro_registry.get(macro_handler_name)
            if macro_data:
                macro_function, macro_parse_rule = macro_data
                return self.handleMacro(fn, macro_function, macro_parse_rule)
            elif fn.expression.name in self.template.template_methods:
                fn.sanitization_state = ast.SanitizedState.SANITIZED_STRING
                if self.template.library:
                    # Calling another library function from this library
                    # function.
                    library_function = fn.expression.name
            elif skip_filter:
                # If the function is marked as skip_filter in the registry, we
                # know it is sanitized.
                fn.sanitization_state = ast.SanitizedState.SANITIZED
            elif skip_filter is False:
                # If the function is marked as skip_filter=False in the
                # registry, we know it is not sanitized.
                fn.sanitization_state = ast.SanitizedState.UNSANITIZED
        elif isinstance(fn.expression, ast.GetUDNNode):
            identifier = [node.name for node in fn.expression.getChildNodes()]
            identifier = '.'.join(identifier)
            if identifier in self.template.library_identifiers:
                # Calling library functions from other templates.
                library_function = '%s.%s' % (identifier, fn.expression.name)

        if library_function:
            # Replace the placeholder node or UDN resolution with a direct
            # reference to the library function, either in another imported
            # module or here.
            fn.expression = ast.IdentifierNode(library_function, pos=pnode.pos)
            # Pass the current template instance into the library function.
            fn.arg_list.child_nodes.insert(0, ast.IdentifierNode('self'))
            # Library functions are spitfire functions so their output is
            # sanitized.
            fn.sanitization_state = ast.SanitizedState.SANITIZED_STRING
            fn.library_function = True

        fn.expression = self.build_ast(fn.expression)[0]
        fn.arg_list = self.build_ast(fn.arg_list)[0]
        return [fn]

    analyzeBufferWrite = analyzeCallFunctionNode

    def analyzeFilterNode(self, pnode):
        fn = pnode
        fn.expression = self.build_ast(fn.expression)[0]
        return [fn]

    # go over the parsed nodes and weed out the parts we don't need
    # it's easier to do this before we morph the AST to look more like python
    def optimize_parsed_nodes(self, node_list):
        optimized_nodes = []
        for n in node_list:
            # strip optional whitespace by removing the nodes
            if (self.options.ignore_optional_whitespace and
                    isinstance(n, ast.OptionalWhitespaceNode)):
                continue
            # collapse adjacent TextNodes so we are calling these buffer writes
            elif (self.options.collapse_adjacent_text and
                  isinstance(n, ast.TextNode) and len(optimized_nodes) and
                  isinstance(optimized_nodes[-1], ast.TextNode)):
                # recreate this object so it doesn't show up as whitespace
                temp_text = ast.TextNode(optimized_nodes[-1].value, pos=n.pos)
                temp_text.parent = optimized_nodes[-1].parent
                temp_text.append_text_node(n)
                optimized_nodes[-1] = temp_text
            else:
                optimized_nodes.append(n)
        # print "optimized_nodes", node_list, optimized_nodes
        return optimized_nodes

    # go over the parsed nodes and weed out the parts we don't need do this
    # after analysis as well, in case a macro generates more ast.BufferWrite
    def optimize_buffer_writes(self, node_list):
        optimized_nodes = ast.NodeList()
        for n in node_list:
            if (self.options.collapse_adjacent_text and is_text_write(n) and
                    len(optimized_nodes) and
                    is_text_write(optimized_nodes[-1])):
                optimized_nodes[-1].append_text_node(n)
            else:
                optimized_nodes.append(n)
        return optimized_nodes

    # Imported modules are trusted to not need UDN resolution.
    def _identifier_can_skip_UDN_resolution(self, identifier):
        if not self.options.skip_import_udn_resolution:
            return False
        return identifier in self.template.trusted_module_identifiers


def is_text_write(node):
    return (isinstance(node, ast.BufferWrite) and
            isinstance(node.expression, ast.LiteralNode))
