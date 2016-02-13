# Copyright 2014 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import unittest

from spitfire.compiler import analyzer
from spitfire.compiler import ast
from spitfire.compiler import compiler
from spitfire.compiler import optimizer
from spitfire.compiler import options
from spitfire.compiler import util
from spitfire.compiler import walker
from spitfire import test_util


class BaseTest(unittest.TestCase):

    def __init__(self, *args):
        unittest.TestCase.__init__(self, *args)
        self.analyzer_options = options.default_options

    def setUp(self):
        self.compiler = compiler.Compiler(
            analyzer_options=self.analyzer_options,
            xspt_mode=False,
            compiler_stack_traces=True)

    def _get_analyzer(self, ast_root):
        optimization_analyzer = optimizer.OptimizationAnalyzer(
            ast_root, self.compiler.analyzer_options, self.compiler)
        optimization_analyzer.visit_ast = test_util.RecordedFunction(
            optimization_analyzer.visit_ast)
        return optimization_analyzer

    def _build_function_template(self):
        """ Build a simple template with a function.

        file: TestTemplate
        #def test_function
        #end def
        """
        ast_root = ast.TemplateNode('TestTemplate')
        function_node = ast.FunctionNode('test_function')
        ast_root.append(function_node)
        return (ast_root, function_node)

    def _build_if_template(self, condition=None):
        """ Build a simple template with a function and an if statement.

        file: TestTemplate
        #def test_function
          #if True
          #end if
        #end def
        """
        ast_root, function_node = self._build_function_template()
        condition_node = condition or ast.LiteralNode(True)
        if_node = ast.IfNode(condition_node)
        function_node.append(if_node)
        return (ast_root, function_node, if_node)

    def _compile(self, template_content):
        template_node = util.parse_template(template_content)
        template_node.source_path = 'test_template.spt'
        return template_node


class TestAnalyzeListLiteralNode(BaseTest):

    def test_list_elements_are_optimized(self):
        self.ast_description = """
        Input:
        [1, 2, 3]
        """

        ast_root = ast.ListLiteralNode('list')
        ast_root.child_nodes.append(ast.LiteralNode(1))
        ast_root.child_nodes.append(ast.LiteralNode(2))
        ast_root.child_nodes.append(ast.LiteralNode(3))

        optimization_analyzer = self._get_analyzer(ast_root)
        optimization_analyzer.visit_ast(ast_root)
        self.assertEqual(len(optimization_analyzer.visit_ast.GetCalls()), 4)


class TestAssignAfterFilterWarning(unittest.TestCase):

    def setUp(self):
        analyzer_options = options.default_options
        analyzer_options.update(cache_resolved_placeholders=True,
                                enable_warnings=True,
                                warnings_as_errors=True)
        self.compiler = compiler.Compiler(analyzer_options=analyzer_options,
                                          xspt_mode=False,
                                          compiler_stack_traces=True)

    def assign_after_filter_fails(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #set $foo = 'foo'
          $foo
          #set $foo = 'bar'
          $foo
        #end def
        """

        ast_root, function_node = self._build_function_template()
        first_assign = ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode('foo'))
        function_node.append(first_assign)
        first_use = ast.FilterNode(ast.IdentifierNode('foo'))
        function_node.append(first_use)
        second_assign = ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode('bar'))
        function_node.append(second_assign)
        second_use = ast.FilterNode(ast.IdentifierNode('foo'))
        function_node.append(second_use)

        optimization_analyzer = optimizer.OptimizationAnalyzer(
            ast_root, self.compiler.analyzer_options, self.compiler)

        optimization_analyzer.visit_ast = test_util.RecordedFunction(
            optimization_analyzer.visit_ast)

        self.assertRaises(compiler.Warning, optimization_analyzer.visit_ast,
                          ast_root)

    def double_assign_ok(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #set $foo = 'foo'
          #set $foo = 'bar'
          $foo
        #end def
        """

        ast_root, function_node = self._build_function_template()
        first_assign = ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode('foo'))
        function_node.append(first_assign)
        second_assign = ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode('bar'))
        function_node.append(second_assign)
        first_use = ast.FilterNode(ast.IdentifierNode('foo'))
        function_node.append(first_use)

        optimization_analyzer = optimizer.OptimizationAnalyzer(
            ast_root, self.compiler.analyzer_options, self.compiler)

        optimization_analyzer.visit_ast = test_util.RecordedFunction(
            optimization_analyzer.visit_ast)

        try:
            optimization_analyzer.visit_ast(ast_root)
        except compiler.Warning:
            self.fail('visit_ast raised WarningError unexpectedly.')


class TestPartialLocalIdentifiers(BaseTest):

    def setUp(self):
        # TODO: Use BaseTest.setUp()?
        analyzer_options = options.default_options
        analyzer_options.update(static_analysis=True,
                                directly_access_defined_variables=True)
        self.compiler = compiler.Compiler(analyzer_options=analyzer_options,
                                          xspt_mode=False,
                                          compiler_stack_traces=True)

    def test_simple_if(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #if True
            #set $foo = 1
          #end if
          $foo
        #end def
        """

        ast_root, function_node, if_node = self._build_if_template()
        assign_node = ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(1))
        if_node.append(assign_node)
        function_node.append(ast.PlaceholderNode('foo'))

        optimization_analyzer = self._get_analyzer(ast_root)
        self.assertRaises(analyzer.SemanticAnalyzerError,
                          optimization_analyzer.visit_ast, ast_root)

    def test_if_partial_else(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #if True
            #set $foo = 1
          #else
            #set $bar = 1
          #end if
          $foo
        #end def
        """

        ast_root, function_node, if_node = self._build_if_template()
        if_node.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(1)))
        if_node.else_.append(ast.AssignNode(
            ast.IdentifierNode('bar'), ast.LiteralNode(1)))
        function_node.append(ast.PlaceholderNode('foo'))

        optimization_analyzer = self._get_analyzer(ast_root)
        self.assertRaises(analyzer.SemanticAnalyzerError,
                          optimization_analyzer.visit_ast, ast_root)

    def test_partial_if_else(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #if True
            #set $foo = 1
          #else
            #set $bar = 1
          #end if
          $bar
        #end def
        """

        ast_root, function_node, if_node = self._build_if_template()
        if_node.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(1)))
        if_node.else_.append(ast.AssignNode(
            ast.IdentifierNode('bar'), ast.LiteralNode(1)))
        function_node.append(ast.PlaceholderNode('bar'))

        optimization_analyzer = self._get_analyzer(ast_root)
        self.assertRaises(analyzer.SemanticAnalyzerError,
                          optimization_analyzer.visit_ast, ast_root)

    def test_nested_else(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #if True
            #set $foo = 1
          #elif
            #set $foo = 2
          #else
            #set $foo = 3
          #end if
          $foo
        #end def
        """

        ast_root, function_node, if_node = self._build_if_template()
        if_node.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(1)))
        if_node_2 = ast.IfNode(ast.LiteralNode(True))
        if_node_2.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(2)))
        if_node_2.else_.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(3)))
        if_node.else_.append(if_node_2)

        function_node.append(ast.PlaceholderNode('foo'))

        optimization_analyzer = self._get_analyzer(ast_root)

        try:
            optimization_analyzer.visit_ast(ast_root)
        except analyzer.SemanticAnalyzerError:
            self.fail('visit_ast raised SemanticAnalyzerError unexpectedly.')

    def test_nested_if(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #if True
            #if True
              #set $foo = 1
            #else
              #set $foo = 2
            #end if
          #else
            #set $foo = 3
          #end if
          $foo
        #end def
        """

        ast_root, function_node, if_node = self._build_if_template()
        if_node_2 = ast.IfNode(ast.LiteralNode(True))
        if_node_2.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(1)))
        if_node_2.else_.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(2)))
        if_node.append(if_node_2)
        if_node.else_.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(3)))
        function_node.append(ast.PlaceholderNode('foo'))

        optimization_analyzer = self._get_analyzer(ast_root)

        try:
            optimization_analyzer.visit_ast(ast_root)
        except analyzer.SemanticAnalyzerError:
            self.fail('visit_ast raised SemanticAnalyzerError unexpectedly.')

    def test_partial_nested_if(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #if True
            #if True
              #set $foo = 1
            #else
              #set $bar = 2
            #end if
          #else
            #set $foo = 3
          #end if
          $foo
        #end def
        """

        ast_root, function_node, if_node = self._build_if_template()
        if_node_2 = ast.IfNode(ast.LiteralNode(True))
        if_node_2.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(1)))
        if_node_2.else_.append(ast.AssignNode(
            ast.IdentifierNode('bar'), ast.LiteralNode(2)))
        if_node.append(if_node_2)
        if_node.else_.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(3)))
        function_node.append(ast.PlaceholderNode('foo'))

        optimization_analyzer = self._get_analyzer(ast_root)
        self.assertRaises(analyzer.SemanticAnalyzerError,
                          optimization_analyzer.visit_ast, ast_root)

    def test_partial_nested_else(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #if True
            #set $foo = 1
          #else
            #if
              #set $bar = 2
            #else
              #set $baz = 3
            #end if
          #end if
          $baz
        #end def
        """

        ast_root, function_node, if_node = self._build_if_template()
        if_node.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(1)))
        if_node_2 = ast.IfNode(ast.LiteralNode(True))
        if_node_2.append(ast.AssignNode(
            ast.IdentifierNode('bar'), ast.LiteralNode(2)))
        if_node_2.else_.append(ast.AssignNode(
            ast.IdentifierNode('baz'), ast.LiteralNode(3)))
        if_node.else_.append(if_node_2)
        function_node.append(ast.PlaceholderNode('baz'))

        optimization_analyzer = self._get_analyzer(ast_root)
        self.assertRaises(analyzer.SemanticAnalyzerError,
                          optimization_analyzer.visit_ast, ast_root)

    def test_partial_nested_else_if(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #if True
            #set $foo = 1
          #else
            #if True
              #set $foo = 2
            #end if
          #end if
          $foo
        #end def
        """

        ast_root, function_node, if_node = self._build_if_template()
        if_node.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(1)))
        if_node_2 = ast.IfNode(ast.LiteralNode(True))
        if_node_2.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(2)))
        if_node.else_.append(if_node_2)
        function_node.append(ast.PlaceholderNode('foo'))

        optimization_analyzer = self._get_analyzer(ast_root)
        self.assertRaises(analyzer.SemanticAnalyzerError,
                          optimization_analyzer.visit_ast, ast_root)

    def test_nested_else(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #if True
            #set $foo = 1
          #else
            #if
              #set $foo = 2
            #else
              #set $foo = 3
            #end if
          #end if
          $foo
        #end def
        """

        ast_root, function_node, if_node = self._build_if_template()
        if_node.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(1)))
        if_node_2 = ast.IfNode(ast.LiteralNode(True))
        if_node_2.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(2)))
        if_node_2.else_.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(3)))
        if_node.else_.append(if_node_2)
        function_node.append(ast.PlaceholderNode('foo'))

        optimization_analyzer = self._get_analyzer(ast_root)

        try:
            optimization_analyzer.visit_ast(ast_root)
        except analyzer.SemanticAnalyzerError:
            self.fail('visit_ast raised SemanticAnalyzerError unexpectedly.')

    def test_nested_partial_use(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #if True
            #set $foo = 1
          #end if
          #if True
            $foo
          #end if
        #end def
        """

        ast_root, function_node, if_node = self._build_if_template()
        if_node.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(1)))
        if_node_2 = ast.IfNode(ast.LiteralNode(True))
        if_node_2.append(ast.PlaceholderNode('foo'))
        function_node.append(if_node_2)

        optimization_analyzer = self._get_analyzer(ast_root)
        self.assertRaises(analyzer.SemanticAnalyzerError,
                          optimization_analyzer.visit_ast, ast_root)


class TestFinalPassHoistConditional(BaseTest):

    def setUp(self):
        analyzer_options = options.default_options
        analyzer_options.update(static_analysis=True,
                                directly_access_defined_variables=True,
                                hoist_conditional_aliases=True,
                                cache_filtered_placeholders=True)
        self.compiler = compiler.Compiler(analyzer_options=analyzer_options,
                                          xspt_mode=False,
                                          compiler_stack_traces=True)

    def test_hoist_both(self):
        self.ast_description = """
        file: TestTemplate
        #global $foo
        #def test_function
          #if True
            $foo
          #else
            $foo
          #end if
        #end def
        """

        def scope_setter(scope):
            scope.local_identifiers.add(ast.IdentifierNode('_rph_foo'))
            scope.aliased_expression_map[ast.PlaceholderNode('foo')] = (
                ast.IdentifierNode('_rph_foo'))
            scope.aliased_expression_map[ast.FilterNode(ast.IdentifierNode(
                '_rph_foo'))] = (ast.IdentifierNode('_fph123'))
            scope.alias_name_set.add('_fph123')
            scope.alias_name_set.add('_rph_foo')

        def build_conditional_body(node):
            node.append(ast.AssignNode(
                ast.IdentifierNode('_rph_foo'), ast.PlaceholderNode('foo')))
            node.append(ast.AssignNode(
                ast.IdentifierNode('_fph123'), ast.FilterNode(
                    ast.IdentifierNode('_rph_foo'))))
            node.append(ast.BufferWrite(ast.IdentifierNode('_fph123')))

        ast_root, function_node, if_node = self._build_if_template()
        ast_root.global_placeholders.add('foo')
        scope_setter(function_node.scope)
        function_node.scope.local_identifiers.add(ast.IdentifierNode('self'))
        scope_setter(if_node.scope)
        scope_setter(if_node.else_.scope)
        build_conditional_body(if_node)
        build_conditional_body(if_node.else_)

        final_pass_analyzer = optimizer.FinalPassAnalyzer(
            ast_root, self.compiler.analyzer_options, self.compiler)

        final_pass_analyzer.hoist = test_util.RecordedFunction(
            final_pass_analyzer.hoist)

        final_pass_analyzer.visit_ast(ast_root)

        # The 4 calls are hoisting the rph alias and the fph alias out of
        # both the if and else clauses.
        self.assertEqual(len(final_pass_analyzer.hoist.GetCalls()), 4)


class TestHoistPlaceholders(BaseTest):

    def setUp(self):
        analyzer_options = options.default_options
        analyzer_options.update(cache_resolved_placeholders=True,
                                enable_warnings=True,
                                warnings_as_errors=True,
                                directly_access_defined_variables=True,
                                static_analysis=False)
        self.compiler = compiler.Compiler(analyzer_options=analyzer_options,
                                          xspt_mode=False,
                                          compiler_stack_traces=True)

    def fake_placeholdernode_replacement(self, placeholder, local_var,
                                         cached_placeholder, local_identifiers):
        return self.analyzer_options.cache_resolved_placeholders

    def _get_analyzer_and_visit(self, ast_root):
        analyzer = self._get_analyzer(ast_root)
        analyzer._placeholdernode_replacement = test_util.RecordedFunction(
            self.fake_placeholdernode_replacement)
        analyzer.visit_ast(ast_root)
        return analyzer

    def test_simple_hoist(self):
        self.ast_description = """
        file: TestTemplate

        #def test_function
          $foo
          $foo
        #end def
        """

        ast_root, function_node = self._build_function_template()
        function_node.append(ast.PlaceholderNode('foo'))
        function_node.append(ast.PlaceholderNode('foo'))

        optimization_analyzer = self._get_analyzer_and_visit(ast_root)
        self.assertEqual(
            optimization_analyzer._placeholdernode_replacement.GetResults(),
            [True, True])

    def test_hoists_both_from_plus(self):
        self.ast_description = """
        file: TestTemplate

        #global $foo

        #def test_function
          #set $bar = $foo + $foo
        #end def
        """

        ast_root, function_node = self._build_function_template()
        ast_root.global_placeholders.add('foo')
        function_node.append(ast.AssignNode(
            ast.IdentifierNode('bar'), ast.BinOpNode('+', ast.PlaceholderNode(
                'foo'), ast.PlaceholderNode('foo'))))

        optimization_analyzer = self._get_analyzer_and_visit(ast_root)
        self.assertEqual(
            optimization_analyzer._placeholdernode_replacement.GetResults(),
            [True, True])

    def test_hoists_lhs_only_from_and(self):
        self.ast_description = """
        file: TestTemplate

        #def test_function
          #if $foo or $bar
          #end if
        #end def
        """

        condition = ast.BinOpNode('or', ast.PlaceholderNode('foo'),
                                  ast.PlaceholderNode('bar'))
        ast_root, function_node, if_node = self._build_if_template(condition)

        optimization_analyzer = self._get_analyzer_and_visit(ast_root)
        self.assertEqual(
            optimization_analyzer._placeholdernode_replacement.GetResults(),
            [True, False])


class TestAssignSlice(BaseTest):

    def test_index_before_assign_error(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #set $foo[1] = 1
        #end def
        """

        ast_root, function_node = self._build_function_template()
        assign_node = ast.AssignNode(
            ast.SliceNode(
                ast.IdentifierNode('foo'), ast.LiteralNode(1)),
            ast.LiteralNode(1))
        function_node.append(assign_node)

        optimization_analyzer = self._get_analyzer(ast_root)
        self.assertRaises(analyzer.SemanticAnalyzerError,
                          optimization_analyzer.visit_ast, ast_root)

    def test_index_after_assign_ok(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #set $foo = {}
          #set $foo[1] = 1
        #end def
        """

        ast_root, function_node = self._build_function_template()
        assign_node1 = ast.AssignNode(
            ast.IdentifierNode('foo'), ast.DictLiteralNode())
        function_node.append(assign_node1)
        assign_node2 = ast.AssignNode(
            ast.SliceNode(
                ast.IdentifierNode('foo'), ast.LiteralNode(1)),
            ast.LiteralNode(1))
        function_node.append(assign_node2)

        optimization_analyzer = self._get_analyzer(ast_root)

        try:
            optimization_analyzer.visit_ast(ast_root)
        except analyzer.SemanticAnalyzerError:
            self.fail('visit_ast raised SemanticAnalyzerError unexpectedly.')

    def test_index_scope_ok(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #set $foo = {}
          #if True
            #set $foo[1] = 1
          #end if
        #end def
        """

        ast_root, function_node = self._build_function_template()
        assign_node1 = ast.AssignNode(
            ast.IdentifierNode('foo'), ast.DictLiteralNode())
        function_node.append(assign_node1)
        if_node = ast.IfNode(ast.LiteralNode(True))
        assign_node2 = ast.AssignNode(
            ast.SliceNode(
                ast.IdentifierNode('foo'), ast.LiteralNode(1)),
            ast.LiteralNode(1))
        if_node.append(assign_node2)
        function_node.append(if_node)

        optimization_analyzer = self._get_analyzer(ast_root)

        try:
            optimization_analyzer.visit_ast(ast_root)
        except analyzer.SemanticAnalyzerError:
            self.fail('visit_ast raised SemanticAnalyzerError unexpectedly.')


class TestCollectWrites(BaseTest):

    def setUp(self):
        analyzer_options = options.default_options
        analyzer_options.update(cache_resolved_placeholders=True,
                                enable_warnings=True,
                                warnings_as_errors=True,
                                directly_access_defined_variables=True,
                                static_analysis=False,
                                batch_buffer_writes=True)
        self.compiler = compiler.Compiler(analyzer_options=analyzer_options,
                                          xspt_mode=False,
                                          compiler_stack_traces=True)

    def _get_analyzer(self, ast_root):
        optimization_analyzer = optimizer.FinalPassAnalyzer(
            ast_root, self.compiler.analyzer_options, self.compiler)
        optimization_analyzer.visit_ast = test_util.RecordedFunction(
            optimization_analyzer.visit_ast)
        return optimization_analyzer

    def test_collect_writes_no_change(self):
        self.ast_description = """
        file: TestTemplate

        #def test_function
          foo
        #end def
        """

        ast_root, function_node = self._build_function_template()
        function_node.append(ast.BufferWrite(ast.LiteralNode('foo')))
        expected_hash = hash(ast_root)

        optimization_analyzer = self._get_analyzer(ast_root)
        got_hash = hash(optimization_analyzer.optimize_ast())
        self.assertEqual(expected_hash, got_hash)

    def test_collect_writes_join_simple(self):
        self.ast_description = """
        file: TestTemplate

        #def test_function
          foo
          bar
        #end def
        """

        ast_root, function_node = self._build_function_template()
        function_node.append(ast.BufferWrite(ast.LiteralNode('foo')))
        function_node.append(ast.BufferWrite(ast.LiteralNode('bar')))
        optimization_analyzer = self._get_analyzer(ast_root)

        ast_root, function_node = self._build_function_template()
        tuple_node = ast.TupleLiteralNode()
        tuple_node.append(ast.LiteralNode('foo'))
        tuple_node.append(ast.LiteralNode('bar'))
        function_node.append(ast.BufferExtend(tuple_node))
        expected_hash = hash(ast_root)

        got_hash = hash(optimization_analyzer.optimize_ast())
        self.assertEqual(expected_hash, got_hash)

    def test_collect_writes_join_if(self):
        self.ast_description = """
        file: TestTemplate

        #def test_function
          foo
          bar
          #if True
            #set $foo = 1
          #end if
          baz
          boo
        #end def
        """

        ast_root, function_node = self._build_function_template()
        function_node.append(ast.BufferWrite(ast.LiteralNode('foo')))
        function_node.append(ast.BufferWrite(ast.LiteralNode('bar')))
        if_node = ast.IfNode()
        if_node.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(1)))
        function_node.append(if_node)
        function_node.append(ast.BufferWrite(ast.LiteralNode('baz')))
        function_node.append(ast.BufferWrite(ast.LiteralNode('boo')))
        optimization_analyzer = self._get_analyzer(ast_root)

        ast_root, function_node = self._build_function_template()
        tuple_node = ast.TupleLiteralNode()
        tuple_node.append(ast.LiteralNode('foo'))
        tuple_node.append(ast.LiteralNode('bar'))
        function_node.append(ast.BufferExtend(tuple_node))
        if_node = ast.IfNode()
        if_node.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(1)))
        function_node.append(if_node)
        tuple_node = ast.TupleLiteralNode()
        tuple_node.append(ast.LiteralNode('baz'))
        tuple_node.append(ast.LiteralNode('boo'))
        function_node.append(ast.BufferExtend(tuple_node))

        expected_hash = hash(ast_root)

        got_hash = hash(optimization_analyzer.optimize_ast())
        self.assertEqual(expected_hash, got_hash)

    def test_duplicate_node_collect(self):
        self.ast_description = """
        file: TestTemplate

        #def test_function
          foo
          bar
          #if True
            #set $foo = 1
          #end if
          baz
          boo
          #if True
            #set $foo = 1
          #end if
        #end def

        NOTE: This test will break if collect_writes is written
        using ast.ASTNode.insert_before.
        """

        ast_root, function_node = self._build_function_template()
        function_node.append(ast.BufferWrite(ast.LiteralNode('foo')))
        function_node.append(ast.BufferWrite(ast.LiteralNode('bar')))
        if_node = ast.IfNode()
        if_node.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(1)))
        function_node.append(if_node)
        function_node.append(ast.BufferWrite(ast.LiteralNode('baz')))
        function_node.append(ast.BufferWrite(ast.LiteralNode('boo')))
        if_node = ast.IfNode()
        if_node.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(1)))
        optimization_analyzer = self._get_analyzer(ast_root)

        ast_root, function_node = self._build_function_template()
        tuple_node = ast.TupleLiteralNode()
        tuple_node.append(ast.LiteralNode('foo'))
        tuple_node.append(ast.LiteralNode('bar'))
        function_node.append(ast.BufferExtend(tuple_node))
        if_node = ast.IfNode()
        if_node.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(1)))
        function_node.append(if_node)
        tuple_node = ast.TupleLiteralNode()
        tuple_node.append(ast.LiteralNode('baz'))
        tuple_node.append(ast.LiteralNode('boo'))
        function_node.append(ast.BufferExtend(tuple_node))
        if_node = ast.IfNode()
        if_node.append(ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(1)))

        expected_hash = hash(ast_root)

        got_hash = hash(optimization_analyzer.optimize_ast())
        self.assertEqual(expected_hash, got_hash)


class TestDoNode(BaseTest):

    def test_do_placeholder_replace(self):
        code = """
        #global $bar

        #def foo
          #do $bar
        #end def
        """

        ast_root = self._compile(code)
        semantic_analyzer = analyzer.SemanticAnalyzer(
            'TestTemplate', ast_root, self.compiler.analyzer_options,
            self.compiler)
        analyzed_tree = semantic_analyzer.get_ast()

        optimization_analyzer = self._get_analyzer(analyzed_tree)
        optimization_analyzer.optimize_ast()


class TestCacheFilterArgs(BaseTest):

    def setUp(self):
        analyzer_options = options.default_options
        analyzer_options.update(cache_resolved_udn_expressions=True,
                                enable_warnings=True,
                                warnings_as_errors=True,
                                directly_access_defined_variables=True,
                                static_analysis=False)
        self.compiler = compiler.Compiler(analyzer_options=analyzer_options,
                                          xspt_mode=False,
                                          compiler_stack_traces=True)

    def test_cache_filter_args_udn(self):
        code = """
        #from foo import bar

        #def func
          $bar.baz('arg')
        #end def
        """

        ast_root = self._compile(code)
        semantic_analyzer = analyzer.SemanticAnalyzer(
            'TestTemplate', ast_root, self.compiler.analyzer_options,
            self.compiler)
        analyzed_tree = semantic_analyzer.get_ast()

        optimization_analyzer = self._get_analyzer(analyzed_tree)
        optimized_tree = optimization_analyzer.optimize_ast()

        def pred(node):
            return type(node) == ast.AssignNode

        alias_assign = walker.find_node(optimized_tree, pred)
        if not alias_assign:
            self.fail('There should be an ast.AssignNode due to caching')

    def test_cache_filter_args_identifier(self):
        code = """
        #implements library
        #from foo import library bar

        #def func
          $bar.baz('arg')
        #end def
        """

        ast_root = self._compile(code)
        semantic_analyzer = analyzer.SemanticAnalyzer(
            'TestTemplate', ast_root, self.compiler.analyzer_options,
            self.compiler)
        analyzed_tree = semantic_analyzer.get_ast()

        optimization_analyzer = self._get_analyzer(analyzed_tree)
        optimized_tree = optimization_analyzer.optimize_ast()

        def pred(node):
            return type(node) == ast.AssignNode
            alias_assign = walker.find_node(optimized_tree, pred)
            if not alias_assign:
                self.fail('There should be an ast.AssignNode due to caching')


class TestFilterInMacro(BaseTest):

    def test_filter_function_macro(self):
        code = """
        #def foo
          $my_macro()
        #end def
        """

        def macro_function(macro_node, arg_map, compiler):
            return '#set $bar = self.filter_function("test")\n'

        self.compiler.register_macro('macro_function_my_macro',
                                     macro_function,
                                     parse_rule='fragment_goal')

        ast_root = self._compile(code)
        semantic_analyzer = analyzer.SemanticAnalyzer(
            'TestTemplate', ast_root, self.compiler.analyzer_options,
            self.compiler)
        analyzed_tree = semantic_analyzer.get_ast()

        optimization_analyzer = self._get_analyzer(analyzed_tree)
        optimized_tree = optimization_analyzer.optimize_ast()

        def pred(node):
            return bool(type(node) == ast.IdentifierNode and node.name ==
                        '_self_filter_function')

        filter_node = walker.find_node(optimized_tree, pred)
        if not filter_node:
            self.fail('Expected _self_filter_function in ast')

    def test_private_filter_function_macro(self):
        code = """
        #def foo
          $my_macro()
        #end def
        """

        def macro_function(macro_node, arg_map, compiler):
            return '#set $bar = self._filter_function("test")\n'

        self.compiler.register_macro('macro_function_my_macro',
                                     macro_function,
                                     parse_rule='fragment_goal')

        ast_root = self._compile(code)
        semantic_analyzer = analyzer.SemanticAnalyzer(
            'TestTemplate', ast_root, self.compiler.analyzer_options,
            self.compiler)
        analyzed_tree = semantic_analyzer.get_ast()

        optimization_analyzer = self._get_analyzer(analyzed_tree)
        optimized_tree = optimization_analyzer.optimize_ast()

        def pred(node):
            return bool(type(node) == ast.IdentifierNode and node.name ==
                        '_self_private_filter_function')

        filter_node = walker.find_node(optimized_tree, pred)
        if not filter_node:
            self.fail('Expected _self_private_filter_function in ast')


class TestHoistOnlyClean(BaseTest):

    def setUp(self):
        analyzer_options = options.o3_options
        self.compiler = compiler.Compiler(analyzer_options=analyzer_options,
                                          xspt_mode=False,
                                          compiler_stack_traces=True)
        self.compiler.new_registry_format = True
        self.compiler.function_name_registry['reg_f'] = ('a.reg_f',
                                                         ['skip_filter'])

    def _get_final_tree(self, code):
        ast_root = self._compile(code)
        semantic_analyzer = analyzer.SemanticAnalyzer(
            'TestTemplate', ast_root, self.compiler.analyzer_options,
            self.compiler)
        analyzed_tree = semantic_analyzer.get_ast()

        optimization_analyzer = self._get_analyzer(analyzed_tree)
        optimized_tree = optimization_analyzer.optimize_ast()

        final_pass_analyzer = optimizer.FinalPassAnalyzer(
            optimized_tree, self.compiler.analyzer_options, self.compiler)

        return final_pass_analyzer.optimize_ast()

    def test_should_hoist_for(self):
        code = """
        #def foo($bar)
          #for $i in []
            $reg_f($bar)
          #end for
        #end def
        """

        final_tree = self._get_final_tree(code)

        def pred(node):
            return type(node) == ast.AssignNode and type(
                node.parent) == ast.FunctionNode

        alias = walker.find_node(final_tree, pred)
        if not alias:
            self.fail(
                'Expected to find ast.AssignNode hoisted to function scope.')

    def test_should_not_hoist_for(self):
        code = """
        #def foo($bar)
          #for $i in []
            #set $bar["1"] = 1
            $reg_f($bar)
          #end for
        #end def
        """

        final_tree = self._get_final_tree(code)

        def pred(node):
            return type(node) == ast.AssignNode and type(
                node.parent) == ast.FunctionNode

        alias = walker.find_node(final_tree, pred)
        if alias:
            self.fail('ast.AssignNode should not be hoisted to function scope.')

    def test_should_hoist_if(self):
        code = """
        #def foo($bar)
          #if True
            $reg_f($bar)
          #else
            $reg_f($bar)
          #end if
        #end def
          """

        final_tree = self._get_final_tree(code)

        def pred(node):
            return type(node) == ast.AssignNode and type(
                node.parent) == ast.FunctionNode

        alias = walker.find_node(final_tree, pred)
        if not alias:
            self.fail(
                'Expected to find ast.AssignNode hoisted to function scope.')

    def test_should_not_hoist_if_do(self):
        code = """
        #def f
        #end def
        #def foo($bar)
          #if True
            #do $f($bar)
            $reg_f($bar)
          #else
            $reg_f($bar)
          #end if
        #end def
        """

        final_tree = self._get_final_tree(code)

        def pred_if(node):
            return type(node) == ast.IfNode

        if_node = walker.find_node(final_tree, pred_if)

        def pred(node):
            return type(node) == ast.AssignNode

        alias = walker.find_node(if_node, pred)
        if not alias:
            self.fail('ast.AssignNode should be present in the If block.')

    def test_should_not_hoist_if_set(self):
        code = """
        #def foo($bar)
          #if True
            #set $bar[1] = 1
            $reg_f($bar)
          #else
            $reg_f($bar)
          #end if
        #end def
        """

        final_tree = self._get_final_tree(code)

        def pred(node):
            return type(node) == ast.AssignNode and type(
                node.parent) == ast.FunctionNode

        alias = walker.find_node(final_tree, pred)
        if alias:
            self.fail(
                'ast.AssignNode should not be hoisted to the ast.FunctionNode.')

    def test_should_not_hoist_if_set_output(self):
        code = """
        #def foo($bar)
          #if True
            #set $bar[1] = 1
            $bar
          #else
            $bar
          #end if
        #end def
        """

        final_tree = self._get_final_tree(code)

        def pred(node):
            return type(node) == ast.AssignNode and type(
                node.parent) == ast.FunctionNode

        alias = walker.find_node(final_tree, pred)
        if alias:
            self.fail(
                'ast.AssignNode should not be hoisted to the ast.FunctionNode.')


class TestSanitizationOptimizations(BaseTest):

    def setUp(self):
        analyzer_options = options.default_options
        self.compiler = compiler.Compiler(analyzer_options=analyzer_options,
                                          xspt_mode=False,
                                          compiler_stack_traces=True,
                                          baked_mode=True)

    def _get_optimized_tree(self, code):
        ast_root = self._compile(code)
        semantic_analyzer = analyzer.SemanticAnalyzer(
            'TestTemplate', ast_root, self.compiler.analyzer_options,
            self.compiler)
        analyzed_tree = semantic_analyzer.get_ast()

        optimization_analyzer = self._get_analyzer(analyzed_tree)
        return optimization_analyzer.optimize_ast()

    def test_should_not_need_sanitization_if(self):
        code = """
        #def foo($bar)
          #if $bar.baz()
            BLAH
          #end if
        #end def
        """

        optimized_tree = self._get_optimized_tree(code)

        def pred(node):
            return type(node) == ast.CallFunctionNode

        call_node = walker.find_node(optimized_tree, pred)
        if not call_node:
            self.fail('Expected to find a ast.CallFunctionNode.')
        if call_node.sanitization_state != ast.SanitizedState.NOT_OUTPUTTED:
            self.fail(
                'Expected node in test expression to not need sanitization.')

    def test_should_not_need_sanitization_do(self):
        code = """
        #def foo($bar)
          #do $bar.baz()
        #end def
        """

        optimized_tree = self._get_optimized_tree(code)

        def pred(node):
            return type(node) == ast.CallFunctionNode

        call_node = walker.find_node(optimized_tree, pred)
        if not call_node:
            self.fail('Expected to find a ast.CallFunctionNode.')
        if call_node.sanitization_state != ast.SanitizedState.NOT_OUTPUTTED:
            self.fail('Expected node in #do to not need sanitization.')

    def test_should_not_need_sanitization_filter(self):
        code = """
        #def foo($bar)
          $bar()
        #end def
        """

        optimized_tree = self._get_optimized_tree(code)

        def pred(node):
            return (type(node) == ast.CallFunctionNode and
                    type(node.parent) == ast.FilterNode)

        call_node = walker.find_node(optimized_tree, pred)
        if not call_node:
            self.fail('Expected to find a ast.CallFunctionNode.')
        if (call_node.sanitization_state !=
                ast.SanitizedState.OUTPUTTED_IMMEDIATELY):
            self.fail(
                'Expected node in ast.FilterNode to not need sanitization.')


if __name__ == '__main__':
    unittest.main()
