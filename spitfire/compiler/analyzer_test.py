# Copyright 2014 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import unittest

from spitfire.compiler import analyzer
from spitfire.compiler import ast
from spitfire.compiler import compiler
from spitfire.compiler import options
from spitfire.compiler import util
from spitfire.compiler import walker
from spitfire import test_util


class BaseTest(unittest.TestCase):

    def __init__(self, *args):
        unittest.TestCase.__init__(self, *args)
        self.analyzer_options = options.default_options
        self.analyzer_options.update(cache_resolved_placeholders=True,
                                     enable_warnings=True,
                                     warnings_as_errors=True)

    def setUp(self):
        self.compiler = compiler.Compiler(
            analyzer_options=self.analyzer_options,
            xspt_mode=False,
            compiler_stack_traces=True)

    def _get_analyzer(self, ast_root):
        semantic_analyzer = analyzer.SemanticAnalyzer(
            'TestTemplate', ast_root, self.compiler.analyzer_options,
            self.compiler)
        semantic_analyzer.get_ast = test_util.RecordedFunction(
            semantic_analyzer.get_ast)
        return semantic_analyzer

    def _build_function_template(self):
        """ Build a simple template with a function.

        file: TestTemplate
        #def test_function
        #end def
        """
        ast_root = ast.TemplateNode('TestTemplate')
        def_node = ast.DefNode('test_function')
        ast_root.append(def_node)
        return (ast_root, def_node)

    def _build_if_template(self, condition=None):
        """ Build a simple template with a function and an if statement.

        file: TestTemplate
        #def test_function
          #if True
          #end if
        #end def
        """
        ast_root, def_node = self._build_function_template()
        condition_node = condition or ast.LiteralNode(True)
        if_node = ast.IfNode(condition_node)
        def_node.append(if_node)
        return (ast_root, def_node, if_node)

    def _compile(self, template_content):
        template_node = util.parse_template(template_content)
        template_node.source_path = 'test_template.spt'
        return template_node


class TestEmptyIfBlockError(BaseTest):

    def test_empty_if_fails(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #if True
          #end if
        #end def
        """

        ast_root, def_node, if_node = self._build_if_template()

        semantic_analyzer = self._get_analyzer(ast_root)

        self.assertRaises(analyzer.SemanticAnalyzerError,
                          semantic_analyzer.get_ast)

    def test_optional_whitespace_if_fails(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #if True

          #end if
        #end def
        """

        ast_root, def_node, if_node = self._build_if_template()
        if_node.append(ast.OptionalWhitespaceNode(' '))

        semantic_analyzer = self._get_analyzer(ast_root)

        self.assertRaises(analyzer.SemanticAnalyzerError,
                          semantic_analyzer.get_ast)

    def test_comment_if_fails(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #if True
            ## This is a comment.
          #end if
        #end def
        """

        ast_root, def_node, if_node = self._build_if_template()
        if_node.append(ast.CommentNode(' This is a comment.'))

        semantic_analyzer = self._get_analyzer(ast_root)

        self.assertRaises(analyzer.SemanticAnalyzerError,
                          semantic_analyzer.get_ast)

    def test_empty_if_full_else_fails(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #if True
          #else
            #set $foo = true
          #end if
        #end def
        """

        ast_root, def_node, if_node = self._build_if_template()
        assign_node = ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(True))
        if_node.else_.append(assign_node)

        semantic_analyzer = self._get_analyzer(ast_root)

        self.assertRaises(analyzer.SemanticAnalyzerError,
                          semantic_analyzer.get_ast)

    def test_empty_elif_fails(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #if True
            #set $foo = True
          #elif False
          #end if
        #end def
        """

        ast_root, def_node, if_node = self._build_if_template()
        assign_node = ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(True))
        if_node.append(assign_node)
        elif_node = ast.IfNode(ast.LiteralNode(False))
        if_node.else_.append(elif_node)
        semantic_analyzer = self._get_analyzer(ast_root)

        self.assertRaises(analyzer.SemanticAnalyzerError,
                          semantic_analyzer.get_ast)

    def test_non_empty_if_ok(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #if True
            #set $foo = True
          #end if
        #end def
        """

        ast_root, def_node, if_node = self._build_if_template()
        assign_node = ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(True))
        if_node.append(assign_node)

        semantic_analyzer = self._get_analyzer(ast_root)

        try:
            semantic_analyzer.get_ast()
        except analyzer.SemanticAnalyzerError:
            self.fail('get_ast raised SemanticAnalyzerError unexpectedly.')


class TestEmptyForBlockError(BaseTest):

    def _build_for_template(self):
        """ Build a simple template with a function and a for loop.

        file: TestTemplate
        #def test_function
          #for $i in []
          #end for
        #end def
        """
        ast_root, def_node = self._build_function_template()
        target_list = ast.TargetListNode()
        target_list.append(ast.PlaceholderNode('foo'))
        expression_list = ast.ExpressionListNode()
        expression_list.append(ast.LiteralNode([]))
        for_node = ast.ForNode(target_list=target_list,
                               expression_list=expression_list)
        def_node.append(for_node)
        return (ast_root, def_node, for_node)

    def test_empty_for_fails(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #for $i in []
          #end for
        #end def
        """

        ast_root, def_node, for_node = self._build_for_template()

        semantic_analyzer = self._get_analyzer(ast_root)

        self.assertRaises(analyzer.SemanticAnalyzerError,
                          semantic_analyzer.get_ast)

    def test_optional_whitespace_for_fails(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #for $i in []

          #end for
        #end def
        """

        ast_root, def_node, for_node = self._build_for_template()
        for_node.append(ast.OptionalWhitespaceNode(' '))

        semantic_analyzer = self._get_analyzer(ast_root)

        self.assertRaises(analyzer.SemanticAnalyzerError,
                          semantic_analyzer.get_ast)

    def test_comment_for_fails(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #for $i in []
            ## This is a comment.
          #end for
        #end def
        """

        ast_root, def_node, for_node = self._build_for_template()
        for_node.append(ast.CommentNode(' This is a comment.'))

        semantic_analyzer = self._get_analyzer(ast_root)

        self.assertRaises(analyzer.SemanticAnalyzerError,
                          semantic_analyzer.get_ast)

    def test_non_empty_for_ok(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #for $i in []
             #set $foo = True
          #end for
        #end def
        """

        ast_root, def_node, for_node = self._build_for_template()
        assign_node = ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(True))
        for_node.append(assign_node)

        semantic_analyzer = self._get_analyzer(ast_root)

        try:
            semantic_analyzer.get_ast()
        except analyzer.SemanticAnalyzerError:
            self.fail('get_ast raised SemanticAnalyzerError unexpectedly.')


class TestGlobalScopeLibraryError(BaseTest):

    def _build_function_template_library(self):
        """ Build a simple library template with a function.

        file: TestTemplate
        #implements library
        #def test_function
        #end def
        """
        ast_root = ast.TemplateNode('TestTemplate')
        implements_node = ast.ImplementsNode('library')
        ast_root.append(implements_node)
        def_node = ast.DefNode('test_function')
        ast_root.append(def_node)
        return (ast_root, def_node)

    def test_library_ok(self):
        self.ast_description = """
        file: TestTemplate
        #implements library
        #def test_function
        #end def
        """

        ast_root, def_node = self._build_function_template_library()

        semantic_analyzer = self._get_analyzer(ast_root)

        try:
            semantic_analyzer.get_ast()
        except analyzer.SemanticAnalyzerError:
            self.fail('get_ast raised SemanticAnalyzerError unexpectedly.')

    def test_set_error(self):
        self.ast_description = """
        file: TestTemplate
        #implements library
        #set $foo = True
        #def test_function
        #end def
        """

        ast_root, def_node = self._build_function_template_library()
        assign_node = ast.AssignNode(
            ast.IdentifierNode('foo'), ast.LiteralNode(True))
        ast_root.insert_before(def_node, assign_node)

        semantic_analyzer = self._get_analyzer(ast_root)

        self.assertRaises(analyzer.SemanticAnalyzerError,
                          semantic_analyzer.get_ast)

    def test_attr_error(self):
        self.ast_description = """
        file: TestTemplate
        #implements library
        #attr $foo = True
        #def test_function
        #end def
        """

        ast_root, def_node = self._build_function_template_library()
        attr_node = ast.AttributeNode('foo', default=ast.LiteralNode(True))
        ast_root.insert_before(def_node, attr_node)

        semantic_analyzer = self._get_analyzer(ast_root)

        self.assertRaises(analyzer.SemanticAnalyzerError,
                          semantic_analyzer.get_ast)

    def test_global_ok(self):
        self.ast_description = """
        file: TestTemplate
        #implements library
        #global $foo
        #def test_function
        #end def
        """

        ast_root, def_node = self._build_function_template_library()
        global_node = ast.GlobalNode('foo')
        ast_root.insert_before(def_node, global_node)

        semantic_analyzer = self._get_analyzer(ast_root)

        try:
            semantic_analyzer.get_ast()
        except analyzer.SemanticAnalyzerError:
            self.fail('get_ast raised SemanticAnalyzerError unexpectedly.')


class TestAssignSlice(BaseTest):

    def test_slice_non_identifier_error(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #set 1[1] = 1
        #end def
        """

        ast_root, def_node = self._build_function_template()
        assign_node = ast.AssignNode(
            ast.SliceNode(
                ast.LiteralNode(1), ast.LiteralNode(1)), ast.LiteralNode(1))
        def_node.append(assign_node)

        semantic_analyzer = self._get_analyzer(ast_root)

        self.assertRaises(analyzer.SemanticAnalyzerError,
                          semantic_analyzer.get_ast)

    def test_slice_identifier_ok(self):
        self.ast_description = """
        file: TestTemplate
        #def test_function
          #set $foo[1] = 1
        #end def
        """

        ast_root, def_node = self._build_function_template()
        assign_node = ast.AssignNode(
            ast.SliceNode(
                ast.IdentifierNode('foo'), ast.LiteralNode(1)),
            ast.LiteralNode(1))
        def_node.append(assign_node)

        semantic_analyzer = self._get_analyzer(ast_root)

        try:
            semantic_analyzer.get_ast()
        except analyzer.SemanticAnalyzerError:
            self.fail('get_ast raised SemanticAnalyzerError unexpectedly.')


class TestSanitizedFunction(BaseTest):

    def setUp(self):
        self.analyzer_options = options.default_options
        self.analyzer_options.update(cache_resolved_placeholders=True,
                                     enable_warnings=True,
                                     warnings_as_errors=True,
                                     baked_mode=True,
                                     generate_unicode=False)
        self.compiler = compiler.Compiler(
            analyzer_options=self.analyzer_options,
            xspt_mode=False,
            compiler_stack_traces=True)
        self.compiler.new_registry_format = True
        self.compiler.function_name_registry['reg_f'] = ('a.reg_f',
                                                         ['skip_filter'])

    def test_template_method_direct(self):
        code = """
        #def foo
          Hello
        #end def

        #def bar
          $foo()
        #end def
        """

        template = self._compile(code)
        semantic_analyzer = self._get_analyzer(template)
        analyzed_ast = semantic_analyzer.get_ast()

        def pred(node):
            return (type(node) == ast.CallFunctionNode and
                    type(node.expression) == ast.PlaceholderNode and
                    node.expression.name == 'foo')

        foo_call = walker.find_node(analyzed_ast, pred)
        if not foo_call:
            self.fail('Expected foo() in ast')
        self.assertEqual(foo_call.sanitization_state,
                         ast.SanitizedState.SANITIZED_STRING)

    def test_library_function_direct(self):
        code = """
        #from module import library my_lib

        #def bar
          $my_lib.foo()
        #end def
        """

        template = self._compile(code)
        semantic_analyzer = self._get_analyzer(template)
        analyzed_ast = semantic_analyzer.get_ast()

        def pred(node):
            return (type(node) == ast.CallFunctionNode and
                    type(node.expression) == ast.IdentifierNode and
                    node.expression.name == 'my_lib.foo')

        foo_call = walker.find_node(analyzed_ast, pred)
        if not foo_call:
            self.fail('Expected my_lib.foo() in ast')
        self.assertEqual(foo_call.sanitization_state,
                         ast.SanitizedState.SANITIZED_STRING)

    def test_library_function_registry_yes(self):
        code = """
        #def bar
          $reg_f()
        #end def
        """

        template = self._compile(code)
        semantic_analyzer = self._get_analyzer(template)
        analyzed_ast = semantic_analyzer.get_ast()

        def pred(node):
            return (type(node) == ast.CallFunctionNode and
                    type(node.expression) == ast.PlaceholderNode and
                    node.expression.name == 'reg_f')

        foo_call = walker.find_node(analyzed_ast, pred)
        if not foo_call:
            self.fail('Expected reg_f() in ast')
        self.assertEqual(foo_call.sanitization_state,
                         ast.SanitizedState.SANITIZED)

    def test_external_function_maybe(self):
        code = """
        #from module import my_lib

        #def bar
          $my_lib.foo()
        #end def
        """

        template = self._compile(code)
        semantic_analyzer = self._get_analyzer(template)
        analyzed_ast = semantic_analyzer.get_ast()

        def pred(node):
            return (type(node) == ast.CallFunctionNode and
                    type(node.expression) == ast.GetUDNNode and
                    type(node.expression.expression) == ast.PlaceholderNode and
                    node.expression.expression.name == 'my_lib' and
                    node.expression.name == 'foo')

        foo_call = walker.find_node(analyzed_ast, pred)
        if not foo_call:
            self.fail('Expected my_libfoo() in ast')
        self.assertEqual(foo_call.sanitization_state,
                         ast.SanitizedState.UNKNOWN)


class TestNoRaw(BaseTest):

    def setUp(self):
        self.analyzer_options = options.default_options
        self.analyzer_options.update(enable_warnings=True,
                                     warnings_as_errors=True,
                                     no_raw=True)
        self.compiler = compiler.Compiler(
            analyzer_options=self.analyzer_options,
            xspt_mode=False,
            compiler_stack_traces=True)

    def test_error_with_raw(self):
        code = """
        #def foo
          #set $a = "a"
          ${a|raw}
        #end def
        """

        template = self._compile(code)
        semantic_analyzer = self._get_analyzer(template)
        self.assertRaises(analyzer.SemanticAnalyzerError,
                          semantic_analyzer.get_ast)

    def test_allow_raw_no_error(self):
        code = """
        #allow_raw
        #def foo
          #set $a = "a"
          ${a|raw}
        #end def
        """

        template = self._compile(code)
        semantic_analyzer = self._get_analyzer(template)
        try:
            semantic_analyzer.get_ast()
        except analyzer.SemanticAnalyzerError:
            self.fail('get_ast raised an error unexpectedly.')

    def test_allow_raw_macro_no_error(self):
        code = """
        #allow_raw
        #global $a
        #def foo
          #i18n()#
            ${a|raw}
          #end i18n#
        #end def
        """

        template = self._compile(code)
        semantic_analyzer = self._get_analyzer(template)
        try:
            semantic_analyzer.get_ast()
        except analyzer.SemanticAnalyzerError:
            self.fail('get_ast raised an error unexpectedly.')

    def test_allow_raw_no_raw_error(self):
        code = """
        #allow_raw
        #def foo
        #end def
        """

        template = self._compile(code)
        semantic_analyzer = self._get_analyzer(template)
        self.assertRaises(analyzer.SemanticAnalyzerError,
                          semantic_analyzer.get_ast)


if __name__ == '__main__':
    unittest.main()
