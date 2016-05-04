# Copyright 2007 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import __builtin__
import copy
import logging
import os.path
import re

from spitfire.compiler import ast
from spitfire.compiler import analyzer
from spitfire.compiler import walker

builtin_names = vars(__builtin__)

_BINOP_INVALID_COUNT = 1000  # Any value > 0 will work.
_BINOP_INITIAL_COUNT = 0
_BINOP_FIRST_PASS = 1


# Utility functions for searching up the tree.
def _get_parent_node_by_pred(node, pred, search_current=False):
    """Find the first parent node that satisfies a predicate function."""
    if not search_current:
        node = node.parent
    while node is not None:
        if pred(node):
            return node
        node = node.parent
    return None


def _get_parent_node_by_type(node, node_type):
    """Find the first parent node that satisfies a specified type or types."""
    return _get_parent_node_by_pred(node, lambda n: isinstance(n, node_type))


def _get_parent_loop(node):
    return _get_parent_node_by_type(node, ast.ForNode)


def _get_parent_block(node):
    return _get_parent_node_by_type(
        node, (ast.FunctionNode, ast.ForNode, ast.IfNode, ast.ElseNode))


def _get_local_identifiers(node):
    local_identifiers = []
    partial_local_identifiers = []
    dirty_local_identifiers = []

    # search the parent scopes
    # fixme: should this be recursive?
    node = node.parent
    while node is not None:
        if isinstance(node, ast.ForNode):
            local_identifiers.extend(node.loop_variant_set)
            local_identifiers.extend(node.scope.local_identifiers)
            partial_local_identifiers.extend(
                node.scope.partial_local_identifiers)
            dirty_local_identifiers.extend(node.scope.dirty_local_identifiers)
        elif isinstance(node, ast.IfNode):
            local_identifiers.extend(node.scope.local_identifiers)
            partial_local_identifiers.extend(
                node.scope.partial_local_identifiers)
            dirty_local_identifiers.extend(node.scope.dirty_local_identifiers)
        elif isinstance(node, ast.ElseNode):
            # in this case, we don't want to go to the parent node, which is the
            # ast.IfNode - we want to go to the parent scope
            local_identifiers.extend(node.scope.local_identifiers)
            partial_local_identifiers.extend(
                node.scope.partial_local_identifiers)
            dirty_local_identifiers.extend(node.scope.dirty_local_identifiers)
            node = node.parent.parent
            continue
        elif isinstance(node, ast.FunctionNode):
            local_identifiers.extend(node.scope.local_identifiers)
            partial_local_identifiers.extend(
                node.scope.partial_local_identifiers)
            dirty_local_identifiers.extend(node.scope.dirty_local_identifiers)
            break
        node = node.parent
    return (frozenset(local_identifiers), frozenset(partial_local_identifiers),
            frozenset(dirty_local_identifiers))


def _get_identifiers_from_expression(node):
    """Find the IdentifierNodes present in an expression.

    This function searches through the nodes of an expression and returns a set
    of the IdentiferNodes that are present. This function doesn't traverse
    ast.GetAttrNode or any LiteralNodes such as ListLiteral or DictLiteral
    nodes.
    """
    return set([n
                for n in walker.flatten_tree(node)
                if isinstance(n, ast.IdentifierNode)])


def _is_clean(node, scope):
    """Determine if the node references any dirty identifiers in the scope.

    If there are any Identifiers in the node that are considered "dirty", this
    function will return False. This is because it is not safe to hoist a node
    that depends on modifications made within its parent scope.
    """
    dirty_identifiers = scope.dirty_local_identifiers
    node_identifiers = _get_identifiers_from_expression(node)
    # There are no dirty idenitifiers in the node being hoisted.
    return not node_identifiers & dirty_identifiers


def _get_common_aliased_expression_map(*scopes):
    """Get the common clean aliased expression map for multiple scopes."""
    if not scopes:
        return {}
    clean_key_sets = []
    for scope in scopes:
        clean_scope_keys = set()
        for alias in scope.aliased_expression_map.iterkeys():
            if _is_clean(alias, scope):
                clean_scope_keys.add(alias)
        clean_key_sets.append(clean_scope_keys)

    common_clean_keys = reduce(lambda x, y: x & y, clean_key_sets)
    return dict([(key, scopes[0].aliased_expression_map[key])
                 for key in common_clean_keys])


# Utility functions for generating names.
def _generate_filtered_placeholder(node):
    """Given a node, generate a name for the cached filtered placeholder"""
    return '_fph%08X' % ast.unsigned_hash(node)


def _generate_cached_resolved_placeholder(node):
    """Given a node, generate a name for the cached udn placeholder"""
    return '_rudn%08X' % ast.unsigned_hash(node)


class _BaseAnalyzer(object):

    def __init__(self, ast_root, options, compiler):
        self.ast_root = ast_root
        self.options = options
        self.compiler = compiler
        self.unoptimized_node_types = set()
        # Used as a flag to determine how many binops we have analyzed.
        self.binop_count = _BINOP_INVALID_COUNT

    def optimize_ast(self):
        self.visit_ast(self.ast_root)
        if self.options.debug:
            print "unoptimized_node_types", self.unoptimized_node_types
        return self.ast_root

    # build an AST node list from a single parse node
    # need the parent in case we are going to delete a node
    def visit_ast(self, node, parent=None):
        node.parent = parent
        method_name = 'analyze%s' % node.__class__.__name__
        method = getattr(self, method_name, self.default_optimize_node)
        if method_name in self.compiler.debug_flags:
            print method_name, node
        return method(node)

    def skip_analyze_node(self, node):
        return

    analyzeLiteralNode = skip_analyze_node
    analyzeIdentifierNode = skip_analyze_node
    analyzeTargetNode = skip_analyze_node

    def default_optimize_node(self, node):
        # print "default_optimize_node", type(node)
        self.unoptimized_node_types.add(type(node))
        return

    # this function has some rules that are a bit unclean - you aren't actually
    # looking for the 'parent' scope, but one you might insert nodes into. for
    # instance, you skip over a ast.ForNode so that optimizetions are inserted
    # in a loop-invariant fashion.
    def get_parent_scope(self, node):
        node_stack = [node]
        node = node.parent
        while node is not None:
            if type(node) == ast.FunctionNode:
                return node.scope
            elif type(node) == ast.IfNode:
                # elements of the test clause need to reference the next scope
                # "up" - usually the function, but could be another conditional
                # block fixme: if we ever implement "elif" this will have to get
                # fixed up
                if node_stack[-1] != node.test_expression:
                    return node.scope
            elif type(node) == ast.ElseNode:
                return node.scope
            elif type(node) == ast.ForNode:
                if node_stack[-1] != node.expression_list:
                    return node.scope
            node_stack.append(node)
            node = node.parent
        self.compiler.error(
            analyzer.SemanticAnalyzerError("expected a parent function"),
            pos=node_stack[-1].pos)

    def get_insert_block_and_point(self, node):
        original_node = node
        insert_marker = node
        node = node.parent
        while node is not None:
            if isinstance(node, (ast.FunctionNode, ast.ForNode, ast.IfNode,
                                 ast.ElseNode)):
                if insert_marker in node.child_nodes:
                    return node, insert_marker

            insert_marker = node
            node = node.parent
        self.compiler.error(
            analyzer.SemanticAnalyzerError("expected a parent block"),
            pos=node.pos)

    def replace_in_parent_block(self, node, new_node):
        insert_block, insert_marker = self.get_insert_block_and_point(node)
        insert_block.replace(insert_marker, new_node)

    def reanalyzeConditionalNode(self, conditional_node):
        if (not self.options.hoist_conditional_aliases and
                not self.options.cache_filtered_placeholders):
            return

        parent_node = conditional_node
        parent_block, insertion_point = self.get_insert_block_and_point(
            conditional_node)

        if self.options.hoist_conditional_aliases:
            #print "reanalyzeConditionalNode", conditional_node
            #print "  parent_block", parent_block
            #print "  parent_scope", parent_block.scope
            # NOTE: need to iterate over items, in case we modify something
            items = conditional_node.scope.aliased_expression_map.items()
            for alias_node, alias in items:
                #print "  check alias:", alias
                #print "    alias_node:", alias_node
                assign_alias_node = ast.AssignNode(alias,
                                                   alias_node,
                                                   pos=alias_node.pos)
                if alias_node in parent_block.scope.aliased_expression_map:
                    if self._is_condition_invariant(alias_node,
                                                    conditional_node):
                        #print "  hoist:", assign_alias_node
                        self.hoist(conditional_node, parent_block,
                                   insertion_point, alias_node,
                                   assign_alias_node)

    def reanalyzeLoopNode(self, loop_node):
        if not self.options.hoist_loop_invariant_aliases:
            return

        parent_block, insertion_point = self.get_insert_block_and_point(
            loop_node)
        # NOTE: need to iterate over items, in case we modify something
        for alias_node, alias in loop_node.scope.aliased_expression_map.items():
            assign_alias = ast.AssignNode(alias, alias_node, pos=alias_node.pos)
            if alias_node in parent_block.scope.aliased_expression_map:
                if self._is_loop_invariant(alias_node, loop_node):
                    self.hoist(loop_node, parent_block, insertion_point,
                               alias_node, assign_alias)
            else:
                # if this alias is not already used in the parent scope, that's
                # ok, hoist it if it's loop invariant
                if self._is_loop_invariant(alias_node, loop_node):
                    loop_node.remove(assign_alias)
                    parent_block.insert_before(loop_node, assign_alias)
                    parent_block.scope.hoisted_aliases.append(alias_node)

    def _is_condition_invariant(self, node, conditional_node):
        """The _is_condition_invariant_legacy function is broken, but seems to
        be correct in some cases. Out of fear and redundancy, in order for
        something to be hoisted, it must pass the old and new tests.
        """
        return (self._is_condition_invariant_legacy(node, conditional_node) and
                _is_clean(node, conditional_node.scope))

    def _is_condition_invariant_legacy(self, node, conditional_node):
        node_dependency_set = self.get_node_dependencies(node)
        condition_invariant = (
            not node_dependency_set & conditional_node.scope.local_identifiers)
        #print "is_condition_invariant:", condition_invariant
        #print "  locals:", conditional_node.scope.local_identifiers
        #print "  deps:", node_dependency_set
        return condition_invariant

    def _is_loop_invariant(self, node, loop_node):
        """The _is_loop_invariant_legacy function is broken, but seems to be
        correct in some cases. Out of fear and redundancy, in order for
        something to be hoisted, it must pass the old and new tests.
        """
        return (self._is_loop_invariant_legacy(node, loop_node) and
                _is_clean(node, loop_node.scope))

    def _is_loop_invariant_legacy(self, node, loop_node):
        node_dependency_set = self.get_node_dependencies(node)
        #     print "is loop invariant node:", node
        #     for x in node_dependency_set:
        #       print "  dep:", x

        # find dependencies within the loop node but outside the node we're
        # checking
        node_dependency_set_except_node_tree = node_dependency_set - set(
            walker.flatten_tree(node))
        dependencies_within_loop = set(walker.flatten_tree(
            loop_node)).intersection(node_dependency_set_except_node_tree)
        depends_on_loop_variants = bool(loop_node.loop_variant_set.intersection(
            node_dependency_set))

        # TODO: Disabling warnings for now. They are useless witout
        # filenames. Also need to make sure all these cases are valid.

        # if not depends_on_loop_variants and dependencies_within_loop:
        #   # we can't assume this is invariant because it depends on other
        #   # nodes inside the loop. eventually we should hoist out both the
        #   # node and its dependencies.
        #   dependency_nodes = '\n'.join('  %s' % node.parent
        #                                for node in dependencies_within_loop)
        #   logging.warning("Cannot hoist possible loop invariant: %s.", node)
        #   logging.warning("Please move following dependencies "
        #                   "out of the loop:\n%s", dependency_nodes)

        return not depends_on_loop_variants and not dependencies_within_loop

    def get_node_dependencies(self, node):
        node_dependency_set = set(walker.flatten_tree(node))
        parent_block = _get_parent_block(node)

        for n in list(node_dependency_set):
            # when this is an identifier, you need to check all of the potential
            # the dependencies for that symbol, which means doing some crawling
            if isinstance(n, ast.IdentifierNode):
                identifier = n
                parent_block_to_check = parent_block
                while parent_block_to_check:
                    for block_node in parent_block_to_check.child_nodes:
                        if isinstance(block_node, ast.AssignNode):
                            if block_node.left == identifier:
                                node_dependency_set.update(
                                    self.get_node_dependencies(
                                        block_node.right))
                                parent_block_to_check = None
                                break
                        elif isinstance(block_node, ast.IfNode):
                            # if you encounter a conditional in your chain, you
                            # depend on any dependencies of the condition itself
                            # FIXME: calling
                            # get_node_dependencies(block_node.test_expression)
                            # causes an infinite loop, but that is probably the
                            # correct way forward to address the dependency
                            # chain
                            node_dependency_set.update(walker.flatten_tree(
                                block_node.test_expression))
                    else:
                        parent_block_to_check = _get_parent_block(
                            parent_block_to_check)
            #elif isinstance(n, (ast.GetUDNNode, ast.FilterNode)):
            #  node_dependency_set.update(
            #    self.get_node_dependencies(node.expression))
            #print "get_node_dependencies", node
            #print "  deps:", node_dependency_set
        return node_dependency_set


class OptimizationAnalyzer(_BaseAnalyzer):

    def analyzeParameterNode(self, parameter):
        self.visit_ast(parameter.default, parameter)
        return

    def analyzeTemplateNode(self, template):
        # If we have a function registry, add in the nodes that we determined
        # are used from the analyzer stage before we begin optimizing.
        for alias in sorted(self.compiler.function_name_registry):
            if alias not in template.used_function_registry_identifiers:
                continue
            fq_name, method = self.compiler.function_name_registry[alias]
            fq_name_parts = fq_name.split('.')
            self.ast_root.from_nodes.append(ast.FromNode(
                [ast.IdentifierNode(x) for x in fq_name_parts[:-1]
                ], ast.IdentifierNode(fq_name_parts[-1]), ast.IdentifierNode(
                    alias)))

        for n in template.from_nodes:
            if n.alias:
                template.global_identifiers.add(n.alias)
            else:
                template.global_identifiers.add(n.identifier)

        # scan extends for dependencies
        # this allows faster calling of template functions - we could also
        # tune ast.BufferWrite calls for these nodes
        if self.options.use_dependency_analysis:
            for n in template.extends_nodes:
                path = os.path.join(
                    *[ident_node.name
                      for ident_node in n.source_module_name_list])
                template_function_names = get_template_functions(
                    self.compiler.include_path, path)
                template.template_methods.update(template_function_names)

        self.visit_ast(template.main_function, template)
        for n in template.child_nodes:
            self.visit_ast(n, template)

    def analyzeFunctionNode(self, function):
        function.scope.local_identifiers.update([ast.IdentifierNode(
            n.name) for n in function.parameter_list])
        # Some binops optimzations can only be done in functions.
        self.binop_count = _BINOP_INITIAL_COUNT
        for n in function.child_nodes:
            self.visit_ast(n, function)
        self.binop_count = _BINOP_INVALID_COUNT

    def analyzeForNode(self, for_node):
        self.visit_ast(for_node.target_list, for_node)
        for_node.loop_variant_set = set(for_node.target_list.flat_list)
        self.visit_ast(for_node.expression_list, for_node)
        for n in for_node.child_nodes:
            self.visit_ast(n, for_node)

    def analyzeAssignNode(self, node):
        scope = self.get_parent_scope(node)
        local_identifiers, _, dirty_identifiers = _get_local_identifiers(node)
        # This is an assignment at an index.
        if isinstance(node.left, ast.SliceNode):
            _identifier = ast.IdentifierNode(node.left.expression.name,
                                             pos=node.pos)
            scope.dirty_local_identifiers.add(_identifier)
            if _identifier not in local_identifiers:
                self.compiler.error(
                    analyzer.SemanticAnalyzerError(
                        'Expression %s being indexed must be defined before use'
                        % _identifier.name),
                    pos=node.pos)
        else:
            _identifier = ast.IdentifierNode(node.left.name, pos=node.pos)
            alias_name = _generate_filtered_placeholder(_identifier)
            if alias_name in scope.alias_name_set:
                if self.options.double_assign_error:
                    self.compiler.error(
                        analyzer.SemanticAnalyzerError(
                            'Multiple assignment of %s' % _identifier.name),
                        pos=node.pos)
                else:
                    self.compiler.warn('Multiple assignment of %s' %
                                       _identifier.name,
                                       pos=node.pos)
            scope.local_identifiers.add(_identifier)
        # note: this hack is here so you can partially analyze alias nodes
        # without double-processing
        if node.right:
            self.visit_ast(node.right, node)

    def analyzeExpressionListNode(self, expression_list_node):
        for n in expression_list_node:
            self.visit_ast(n, expression_list_node)

    def analyzeTargetListNode(self, target_list_node):
        flat_list = []
        for n in target_list_node:
            self.visit_ast(n, target_list_node)
            if type(n) == ast.TargetListNode:
                flat_list.extend(n.flat_list)
            else:
                flat_list.append(n)
        target_list_node.flat_list = flat_list

#   def analyzeParameterListNode(self, parameter_list_node):
#     flat_list = []
#     for n in parameter_list_node:
#       flat_list.append(n)
#     target_list_node.flat_list = flat_list

    def analyzeArgListNode(self, arg_list_node):
        scope = self.get_parent_scope(arg_list_node)
        for n in arg_list_node:
            # If an identifier is passed into a function and we are not in a
            # filter node, mark it as dirty. Filter nodes are always written
            # out, therefore we don't consider the final call a modification.
            # This assumption is predictaed on the fact that you can't modify a
            # variable once it has been written.
            if not _get_parent_node_by_type(arg_list_node, ast.FilterNode):
                if isinstance(n, ast.PlaceholderNode):
                    scope.dirty_local_identifiers.add(ast.IdentifierNode(
                        n.name))
                if isinstance(n, ast.ParameterNode) and isinstance(
                        n.default, ast.PlaceholderNode):
                    scope.dirty_local_identifiers.add(ast.IdentifierNode(
                        n.default.name))
            self.visit_ast(n, arg_list_node)

    def analyzeTupleLiteralNode(self, tuple_literal_node):
        for n in tuple_literal_node.child_nodes:
            self.visit_ast(n, tuple_literal_node)

    def analyzeDictLiteralNode(self, dict_literal_node):
        for key_node, value_node in dict_literal_node.child_nodes:
            self.visit_ast(key_node, dict_literal_node)
            self.visit_ast(value_node, dict_literal_node)

    def analyzeListLiteralNode(self, list_literal_node):
        for n in list_literal_node.child_nodes:
            self.visit_ast(n, list_literal_node)

    def analyzeDoNode(self, do_node):
        self.visit_ast(do_node.expression, do_node)

    def analyzeCallFunctionNode(self, function_call):
        # If the ast.CallFunctionNode is in the test expression of an
        # ast.IfNode, do not wrap the function with a SanitizedPlaceholder.
        def is_in_test_expression(node):
            return (isinstance(node.parent, ast.IfNode) and
                    node == node.parent.test_expression)

        if _get_parent_node_by_pred(function_call,
                                    is_in_test_expression,
                                    search_current=True):
            function_call.sanitization_state = ast.SanitizedState.NOT_OUTPUTTED
        # If the ast.CallFunctionNode is in a ast.DoNode, do not wrap the
        # function with a SanitizedPlaceholder.
        if _get_parent_node_by_type(function_call, ast.DoNode):
            function_call.sanitization_state = ast.SanitizedState.NOT_OUTPUTTED

        self.visit_ast(function_call.expression, function_call)
        self.visit_ast(function_call.arg_list, function_call)

    # NOTE: these optimizations are disabled because the optimizer has a
    # tendency to "over-hoist" code inside a ast.CacheNode and you end up doing
    # *more* work
    def analyzeCacheNode(self, cache_node):
        cache_placeholders = self.options.cache_resolved_placeholders
        cache_udn_expressions = self.options.cache_resolved_udn_expressions
        cache_filtered_placeholders = self.options.cache_filtered_placeholders
        self.options.cache_resolved_placeholders = False
        self.options.cache_resolved_udn_expressions = False
        self.options.cache_filtered_placeholders = False

        self.visit_ast(cache_node.expression, cache_node)

        self.options.cache_resolved_placeholders = cache_placeholders
        self.options.cache_resolved_udn_expressions = cache_udn_expressions
        self.options.cache_filtered_placeholders = cache_filtered_placeholders

    def analyzeBufferWrite(self, buffer_write):
        self.visit_ast(buffer_write.expression, buffer_write)
        # template functions output text - don't format them as strings
        if (isinstance(buffer_write.expression, ast.BinOpNode) and
                buffer_write.expression.operator == '%' and
                isinstance(buffer_write.expression.right, ast.CallFunctionNode)
                and isinstance(buffer_write.expression.right.expression,
                               ast.TemplateMethodIdentifierNode)):
            buffer_write.replace(buffer_write.expression,
                                 buffer_write.expression.right)

    def analyzeEchoNode(self, node):
        for n in (node.test_expression, node.true_expression,
                  node.false_expression):
            if n:
                self.visit_ast(n, node)

    def analyzeFilterNode(self, filter_node):
        self.visit_ast(filter_node.expression, filter_node)

        if isinstance(filter_node.expression, ast.CallFunctionNode):
            # If a ast.FilterNode has a ast.CallFunctionNode as an expression,
            # let the filter node handle determining if filtering should occur,
            # rather than the sanitization wrapper.
            filter_node.expression.sanitization_state = (
                ast.SanitizedState.OUTPUTTED_IMMEDIATELY)

        if (isinstance(filter_node.expression, ast.CallFunctionNode) and
                isinstance(filter_node.expression.expression,
                           ast.TemplateMethodIdentifierNode)):
            filter_node.parent.replace(filter_node, filter_node.expression)
            return

        # A ast.CallFunctionNode will require passing in both the value and the
        # function to the filter_function. If the ast.CallFunctionNode's
        # expression is a ast.GetUDNNode, we can avoid looking up the attribute
        # twice by caching its value. This is also true if the
        # ast.CallFunctionNode's expression is an ast.IdentifierNode with a '.'
        # in the name.
        if isinstance(filter_node.expression, ast.CallFunctionNode):
            fn_node = filter_node.expression
            if (self.options.cache_resolved_udn_expressions and
                    isinstance(fn_node.expression, ast.IdentifierNode) and
                    '.' in fn_node.expression.name):
                scope = self.get_parent_scope(filter_node)
                udn_node = fn_node.expression
                # For some udn style node, create a cached variable. ex.
                # _rudn12345
                alias_name = _generate_cached_resolved_placeholder(udn_node)
                alias = ast.IdentifierNode(alias_name, pos=filter_node.pos)
                scope.local_identifiers.add(alias)
                # Create an assignment node that assigns the udn node to the
                # ast.IdentifierNode.
                assign_alias = ast.AssignNode(alias,
                                              udn_node,
                                              pos=filter_node.pos)
                insert_block, insert_marker = self.get_insert_block_and_point(
                    filter_node)
                # Insert the assignment before the ast.FilterNode
                insert_block.insert_before(insert_marker, assign_alias)
                # Replace the udn node in the ast.CallFunctionNode with the
                # alias.
                filter_node.expression.replace(udn_node, alias)

        if self.options.cache_filtered_placeholders:
            # NOTE: you *must* analyze the node before putting it in a dict
            # otherwise the definition of hash and equivalence will change and
            # the node will not be found due to the sketchy custom hash function
            scope = self.get_parent_scope(filter_node)
            alias = scope.aliased_expression_map.get(filter_node)

            if not alias:
                alias_name = _generate_filtered_placeholder(
                    filter_node.expression)
                if alias_name in scope.alias_name_set:
                    print "duplicate alias_name", alias_name
                    print "scope", scope
                    print "scope.alias_name_set", scope.alias_name_set
                    print " ".join("scope.aliased_expression_map",
                                   scope.aliased_expression_map)
                    return

                alias = ast.IdentifierNode(alias_name, pos=filter_node.pos)
                scope.alias_name_set.add(alias_name)
                scope.aliased_expression_map[filter_node] = alias
                assign_alias = ast.AssignNode(alias,
                                              filter_node,
                                              pos=filter_node.pos)

                insert_block, insert_marker = self.get_insert_block_and_point(
                    filter_node)
                insert_block.insert_before(insert_marker, assign_alias)

            filter_node.parent.replace(filter_node, alias)

    def _placeholdernode_replacement(self, placeholder, local_var,
                                     cached_placeholder, local_identifiers):
        """This function tries to replace a ast.PlaceholderNode with a node type
        that does not need to be resolved such as an ast.IdentifierNode or a
        cached placeholder.
        """
        if local_var in local_identifiers:
            placeholder.parent.replace(placeholder, local_var)
        elif placeholder.name in self.ast_root.template_methods:
            placeholder.parent.replace(
                placeholder, ast.TemplateMethodIdentifierNode(placeholder.name))
        elif local_var in self.ast_root.global_identifiers:
            placeholder.parent.replace(placeholder, local_var)
        elif cached_placeholder in local_identifiers:
            placeholder.parent.replace(placeholder, cached_placeholder)
        elif local_var.name in builtin_names:
            placeholder.parent.replace(placeholder,
                                       ast.IdentifierNode(local_var.name))
        elif self.options.cache_resolved_placeholders:
            scope = self.get_parent_scope(placeholder)
            scope.alias_name_set.add(cached_placeholder.name)
            scope.aliased_expression_map[placeholder] = cached_placeholder

            insert_block, insert_marker = self.get_insert_block_and_point(
                placeholder)
            # note: this is sketchy enough that it requires some explanation
            # basically, you need to visit the node for the parent function to
            # get the memo that this value is aliased. unfortunately, the naive
            # case of just calling visit_ast blows up since it tries to double
            # analyze a certain set of nodes. you only really need to analyze
            # that the assignment took place, then you can safely alias the
            # actual function call. definitely sketchy, but it does seem to work
            assign_rph = ast.AssignNode(cached_placeholder,
                                        None,
                                        pos=placeholder.pos)
            cached_placeholder.parent = assign_rph
            #print "optimize scope:", insert_block
            #print "optimize marker:", insert_marker
            insert_block.insert_before(insert_marker, assign_rph)
            self.visit_ast(assign_rph, insert_block)
            assign_rph.right = placeholder
            placeholder.parent.replace(placeholder, cached_placeholder)

    def analyzePlaceholderNode(self, placeholder):
        if self.options.directly_access_defined_variables:
            # when the analyzer finds a ast.PlaceholderNode and generates a
            # function call out of it, i annotate an ast.IdentifierNode with the
            # original placeholder name
            local_var = ast.IdentifierNode(placeholder.name,
                                           pos=placeholder.pos)
            cached_placeholder = ast.IdentifierNode('_rph_%s' % local_var.name,
                                                    pos=placeholder.pos)
            (local_identifiers, partial_local_identifiers, _) = (
                _get_local_identifiers(placeholder))
            attrs = set([ast.IdentifierNode(node.name)
                         for node in self.ast_root.attr_nodes])
            non_local_identifiers = (
                partial_local_identifiers - local_identifiers - attrs)
            if (self.options.static_analysis and
                    local_var in non_local_identifiers):
                self.compiler.error(
                    analyzer.SemanticAnalyzerError(
                        ('Variable %s is not guaranteed to be in scope. '
                         'Define the variable in all branches of the '
                         'conditional or before the conditional.') % local_var),
                    pos=placeholder.pos)
            # print "local_identifiers", local_identifiers
            self._placeholdernode_replacement(
                placeholder, local_var, cached_placeholder, local_identifiers)

    def analyzePlaceholderSubstitutionNode(self, placeholder_substitution):
        self.visit_ast(placeholder_substitution.expression,
                       placeholder_substitution)

#   def alias_expression_in_function(self, function, expression):
#     alias = function.aliased_expression_map.get(expression)
#     if not alias:
#       alias_name = '_%s' % (expression.name)
#       if alias_name in function.alias_name_set:
#         print "duplicate alias_name", alias_name
#         return

#       alias = ast.IdentifierNode(alias_name)
#       function.aliased_expression_map[expression] = alias
#       assign_alias = ast.AssignNode(alias, expression)
#       parent_loop = _get_parent_loop(node)
#       # fixme: check to see if this expression is loop-invariant
#       # must add a test case for this
#       child_node_set = set(node.getChildNodes())
#       #print "child_node_set", child_node_set
#       #print "parent_loop", parent_loop, "parent", node.parent
#       if (parent_loop is not None and
#           not parent_loop.loop_variant_set.intersection(child_node_set)):
#         #print "pull up loop invariant", assign_alias
#         parent_loop.parent.insert_before(parent_loop, assign_alias)
#       else:
#         insert_block, insert_marker = self.get_insert_block_and_point(node)
#         insert_block.insert_before(insert_marker, assign_alias)

#     node.parent.replace(node, alias)

    def analyzeGetAttrNode(self, node):
        if not self.options.alias_invariants:
            return

        # fixme: only handle the trivial case for now
        # simplifies the protocol for making up alias names
        if type(node.expression) != ast.IdentifierNode:
            return

        scope = self.get_parent_scope(node)
        alias = scope.aliased_expression_map.get(node)

        if not alias:
            if node.expression.name[0] != '_':
                alias_format = '_%s_%s'
            else:
                alias_format = '%s_%s'
            alias_name = alias_format % (node.expression.name, node.name)
            if alias_name in scope.alias_name_set:
                print "duplicate alias_name", alias_name
                print "scope", scope
                print "scope.alias_name_set", scope.alias_name_set
                print " ".join("scope.aliased_expression_map",
                               scope.aliased_expression_map)
                return

            alias = ast.IdentifierNode(alias_name)
            scope.alias_name_set.add(alias_name)
            scope.aliased_expression_map[node] = alias
            assign_alias = ast.AssignNode(alias, node)

            parent_loop = _get_parent_loop(node)
            # fixme: check to see if this expression is loop-invariant
            # must add a test case for this
            child_node_set = set(node.getChildNodes())
            #print "child_node_set", child_node_set
            #print "parent_loop", parent_loop, "parent", node.parent
            if (self.options.inline_hoist_loop_invariant_aliases and
                    parent_loop is not None and
                    not parent_loop.loop_variant_set.intersection(
                        child_node_set)):
                # print "pull up loop invariant", assign_alias
                parent_loop.parent.insert_before(parent_loop, assign_alias)
            else:
                insert_block, insert_marker = self.get_insert_block_and_point(
                    node)
                insert_block.insert_before(insert_marker, assign_alias)

        node.parent.replace(node, alias)

    def analyzeIfNode(self, if_node):
        self.visit_ast(if_node.test_expression, if_node)

        for n in if_node.child_nodes:
            self.visit_ast(n, if_node)

        for n in if_node.else_.child_nodes:
            self.visit_ast(n, if_node.else_)

        parent_scope = self.get_parent_scope(if_node)
        if_scope_vars = if_node.scope.local_identifiers

        # once both branches are optimized, walk the scopes for any variables
        # that are defined in both places. those will be promoted to function
        # scope since it is safe to assume that those will defined fixme: this
        # feels like a bit of hack - but not sure how to do this correctly
        # without reverting to slower performance for almost all calls to
        # resolve_placeholder.
        #
        # it seems like certain optimizations need to be hoisted up to the
        # parent scope. this is particularly the case when you are aliasing
        # common functions that are likely to occur in the parent scope after
        # the conditional block. you *need* to hoist those, or you will have
        # errors when the branch fails. essentially you have to detect and hoist
        # 'branch invariant' optimizations.
        #
        # TODO: we can try to hoist up invariants if they don't depend on the
        # condition. this is somewhat hard to know, so the best way to do so
        # without multiple passes of the optimizer is to hoist only things that
        # were already defined in the parent scope - like _buffer, or things on
        # self.
        if if_node.else_.child_nodes:
            common_local_identifiers = (if_scope_vars
                                        & if_node.else_.scope.local_identifiers)
            # The set of nodes that are not defined in both the if and else
            # branches.
            partial_local_identifiers = (
                (if_scope_vars ^ if_node.else_.scope.local_identifiers)
                | if_node.scope.partial_local_identifiers
                | if_node.else_.scope.partial_local_identifiers)

            common_alias_name_set = (if_node.scope.alias_name_set
                                     & if_node.else_.scope.alias_name_set)

            # Only promote aliased expressions to the parent scope when the
            # alias would be used in both the if and else branches.
            common_aliased_expression_map = _get_common_aliased_expression_map(
                if_node.scope, if_node.else_.scope)

            parent_scope.local_identifiers.update(common_local_identifiers)
            parent_scope.alias_name_set.update(common_alias_name_set)
            parent_scope.aliased_expression_map.update(
                common_aliased_expression_map)
        else:
            partial_local_identifiers = if_scope_vars

        non_parent_scope_identifiers = (
            partial_local_identifiers - parent_scope.local_identifiers)
        parent_scope.partial_local_identifiers.update(
            non_parent_scope_identifiers)
        # Any variable considered dirty in an if or else block should be dirty
        # in the parent scope as well.
        if_dirty_identifiers = if_node.scope.dirty_local_identifiers
        else_dirty_identifiers = if_node.else_.scope.dirty_local_identifiers
        parent_scope.dirty_local_identifiers.update(if_dirty_identifiers)
        parent_scope.dirty_local_identifiers.update(else_dirty_identifiers)

    def analyzeBinOpNode(self, n):
        # if you are trying to use short-circuit behavior, these two
        # optimizations can sabotage correct execution since the rhs may be
        # hoisted above the ast.IfNode and cause it to get executed prior to
        # passing the lhs check.
        should_visit_left = True
        and_or_operator = n.operator in ('and', 'or')
        if and_or_operator:
            self.binop_count += 1
            cache_placeholders = self.options.cache_resolved_placeholders
            cache_udn_expressions = self.options.cache_resolved_udn_expressions
            # If this is the first binop, we can visit the LHS since that must
            # always be executed.
            if self.binop_count == _BINOP_FIRST_PASS:
                self.visit_ast(n.left, n)
                should_visit_left = False
            self.options.cache_resolved_placeholders = False
            self.options.cache_resolved_udn_expressions = False

        if should_visit_left:
            self.visit_ast(n.left, n)
        self.visit_ast(n.right, n)

        if and_or_operator:
            self.binop_count -= 1
            self.options.cache_resolved_placeholders = cache_placeholders
            self.options.cache_resolved_udn_expressions = cache_udn_expressions

    analyzeBinOpExpressionNode = analyzeBinOpNode

    def analyzeUnaryOpNode(self, op_node):
        self.visit_ast(op_node.expression, op_node)

    def analyzeGetUDNNode(self, node):
        if not self.options.prefer_whole_udn_expressions:
            self.visit_ast(node.expression, node)

        # If self._filter_function is created in a macro, make sure we rename
        # it.
        self_node = ast.IdentifierNode('self')
        if node.expression == self_node and node.name == '_filter_function':
            alias = ast.IdentifierNode('_self_private_filter_function',
                                       pos=node.pos)
            node.parent.replace(node, alias)
            return
        # If self.filter_function is created in a macro, make sure we rename it.
        if node.expression == self_node and node.name == 'filter_function':
            alias = ast.IdentifierNode('_self_filter_function', pos=node.pos)
            node.parent.replace(node, alias)
            return

        if self.options.cache_resolved_udn_expressions:
            cached_udn = ast.IdentifierNode(
                _generate_cached_resolved_placeholder(node),
                pos=node.pos)
            (local_identifiers, _, _) = _get_local_identifiers(node)
            if cached_udn in local_identifiers:
                node.parent.replace(node, cached_udn)
            else:
                insert_block, insert_marker = self.get_insert_block_and_point(
                    node)

                # if there is a reassignment in the parent block, don't cache
                # this incase it needs to be re-resolved.
                # #set $text = $text.replace('\r\n', '\n')
                # #set $text = $text.replace('\t', '  ')
                # in this example, if you cache the udn expression text.replace,
                # you have a problem - you won't ever use the new string create
                # by the first call to replace
                for child_node in insert_block.child_nodes:
                    if (isinstance(child_node, ast.AssignNode) and
                            child_node.left == node.expression):
                        return

                scope = self.get_parent_scope(node)
                scope.alias_name_set.add(cached_udn.name)
                scope.aliased_expression_map[node] = cached_udn

                # note: this is sketchy enough that it requires some explanation
                # basically, you need to visit the node for the parent function
                # to get the memo that this value is aliased. unfortunately, the
                # naive case of just calling visit_ast blows up since it tries
                # to double analyze a certain set of nodes. you only really need
                # to analyze that the assignment took place, then you can safely
                # alias the actual function call. definitely sketchy, but it
                # does seem to work
                assign_rph = ast.AssignNode(cached_udn, None, pos=node.pos)
                cached_udn.parent = assign_rph
                insert_block.insert_before(insert_marker, assign_rph)
                self.visit_ast(assign_rph, insert_block)
                assign_rph.right = node
                node.parent.replace(node, cached_udn)
        elif self.options.prefer_whole_udn_expressions:
            self.visit_ast(node.expression, node)

    def analyzeSliceNode(self, pnode):
        self.visit_ast(pnode.expression, pnode)
        self.visit_ast(pnode.slice_expression, pnode)


# a second pass over the optimized tree to hoist invariant aliases to their
# parent blocks
class FinalPassAnalyzer(_BaseAnalyzer):

    def analyzeTemplateNode(self, template):
        self.visit_ast(template.main_function, template)
        for n in template.child_nodes:
            self.visit_ast(n, template)

    def analyzeFunctionNode(self, function):
        for n in function.child_nodes:
            self.visit_ast(n, function)
        if self.options.batch_buffer_writes:
            self.collect_writes(function)

    def analyzeForNode(self, for_node):
        for n in for_node.child_nodes:
            self.visit_ast(n, for_node)

        self.reanalyzeLoopNode(for_node)
        if self.options.batch_buffer_writes:
            self.collect_writes(for_node)

    def analyzeIfNode(self, if_node):
        # depth-first
        for n in if_node.child_nodes:
            self.visit_ast(n, if_node)

        for n in if_node.else_.child_nodes:
            self.visit_ast(n, if_node.else_)

        self.reanalyzeConditionalNode(if_node)
        self.reanalyzeConditionalNode(if_node.else_)
        if self.options.batch_buffer_writes:
            self.collect_writes(if_node)
            self.collect_writes(if_node.else_)

    def analyzeBufferWrite(self, buffer_write):
        """Perform ast.BufferWrite optimizations.

    Do this in the final pass optimizer to make sure that the
    optimization is handled after caching placeholders.
    """
        self.visit_ast(buffer_write.expression, buffer_write)
        # All filterning is done before writing to the buffer. If the function
        # output needed filtering then it would be wrapped in a ast.FilterNode.
        if isinstance(buffer_write.expression, ast.CallFunctionNode):
            buffer_write.expression.sanitization_state = (
                ast.SanitizedState.OUTPUTTED_IMMEDIATELY)

    def hoist(self, parent_node, parent_block, insertion_point, alias_node,
              assign_alias_node):

        # prune the implementation in the nested block
        # print "prune", alias_node
        # print " ".join("parent_block aliases",
        #                parent_block.scope.aliased_expression_map)
        parent_node.remove(assign_alias_node)
        # if we've already hoisted an assignment, don't do it again
        if alias_node not in parent_block.scope.hoisted_aliases:
            # prune the original implementation in the current block and
            # reinsert the alias before it's first potential usage if it
            # is needed earlier in the execution path.
            # when a variable aliased in both the if and
            # else blocks is promoted to the parent scope
            # the implementation isn't actually hoisted (should it be?)
            # inline with the ast.IfNode optimization so we need to check if the
            # node is already here
            if assign_alias_node in parent_block.child_nodes:
                current_pos = parent_block.child_nodes.index(assign_alias_node)
                # an else node's parent is the ast.IfNode, which is the relevant
                # node when searching for the insertion point
                needed_pos = parent_block.child_nodes.index(insertion_point)
                if needed_pos < current_pos:
                    parent_block.child_nodes.remove(assign_alias_node)
                    if isinstance(parent_node, ast.ElseNode):
                        parent_block.insert_before(parent_node.parent,
                                                   assign_alias_node)
                    else:
                        parent_block.insert_before(parent_node,
                                                   assign_alias_node)
                    # print "insert_before", alias_node
            else:
                # still need to insert the alias
                parent_block.insert_before(insertion_point, assign_alias_node)
            parent_block.scope.hoisted_aliases.append(alias_node)

        # NOTE: once we hoist an expression, we need to make sure that we no
        # longer use this for dependencies in the current scope
        del parent_node.scope.aliased_expression_map[alias_node]
        parent_node.scope.alias_name_set.remove(assign_alias_node.left.name)
        # FIXME: this is probably an indication of a bug or unnecessary
        # difference between the caching of placeholders and filter expressions
        if not isinstance(alias_node, ast.FilterNode):
            parent_node.scope.local_identifiers.remove(assign_alias_node.left)

    def make_write_node(self, write_list):
        """Convert a list of expressions to be written into a single
        ast.ASTNode. This will return either be a ast.BufferWrite node, a
        ast.BufferExtend node or None if write_list is empty.
        """
        if not write_list:
            return None
        # If there is only a single node, avoid the overhead of
        # constructing a tuple.
        if len(write_list) == 1:
            return ast.BufferWrite(write_list[0])
        tuple_node = ast.TupleLiteralNode()
        for exp in write_list:
            tuple_node.append(exp)
        return ast.BufferExtend(tuple_node)

    def collect_writes(self, node):
        """Look at all the writes that are children of the node and move them to
        the latest place they can be safely placed. This means that it either
        goes before an (if/function/loop) or at the end of the list of nodes.
        Once they are all together, they can be batched into a buffer.extend
        operation. This avoids list resize operations.
        """

        passable_nodes = (ast.AssignNode, ast.CacheNode)

        # ast.ASTNode.insert_before is broken in a way that if there are
        # duplicate nodes, inserts always occur before the first one. To
        # deal with this, we construct a new ast.NodeList rather than
        # modifying the original one.
        old_node_list = node.child_nodes
        node.child_nodes = ast.NodeList()

        write_list = []
        for n in old_node_list:
            if isinstance(n, ast.BufferWrite):
                write_list.append(n.expression)
            elif isinstance(n, ast.BufferExtend):
                write_list.extend(n.expression.child_nodes)
            elif not isinstance(n, passable_nodes):
                write_node = self.make_write_node(write_list)
                if write_node:
                    node.append(write_node)
                write_list = []
                node.append(n)
            else:
                node.append(n)
        write_node = self.make_write_node(write_list)
        if write_node:
            node.append(write_node)


template_function_re = re.compile('^[^#]*#(def|block)\s+(\w+)')
extends_re = re.compile('^#extends\s+([\.\w]+)')
template_extensions = ('.spt', '.tmpl')


def _extend_to_real_path(base_dir, ex_path):
    for ext in template_extensions:
        rpath = os.path.join(base_dir, ex_path) + ext
        if os.path.exists(rpath):
            return rpath
    raise Exception(
        'could not find .spt or .tmpl file for %s during dependency check' %
        ex_path)


# scan an spt file for template functions it will output
def get_template_functions(base_dir, path):
    template_function_names = set()
    path = _extend_to_real_path(base_dir, path)
    if not path:
        return template_function_names
    f = open(path)
    for line in f:
        match = template_function_re.match(line)
        if match:
            template_function_names.add(match.group(2))
            continue
        match = extends_re.match(line)
        if match:
            extend_name = match.group(1)
            extend_path = extend_name.replace('.', '/')
            template_function_names.update(get_template_functions(base_dir,
                                                                  extend_path))
    f.close()
    return template_function_names
