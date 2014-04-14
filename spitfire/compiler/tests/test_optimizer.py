import unittest
from spitfire.compiler.ast import *
from spitfire.compiler import analyzer
from spitfire.compiler import util
from spitfire.compiler import optimizer


class TestAnalyzeListLiteralNode(unittest.TestCase):

  def setUp(self):
    self.compiler = util.Compiler(
        analyzer_options=analyzer.default_options,
        xspt_mode=False)

  def test_list_elements_are_optimized(self):
    self.ast_description = """
    Input:
    [1, 2, 3]
    """
    ast_root = ListLiteralNode('list')
    ast_root.child_nodes.append(LiteralNode(1))
    ast_root.child_nodes.append(LiteralNode(2))
    ast_root.child_nodes.append(LiteralNode(3))

    optimization_analyzer = optimizer.OptimizationAnalyzer(
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    optimization_analyzer.visit_ast = unittest.RecordedFunction(
        optimization_analyzer.visit_ast)

    optimization_analyzer.visit_ast(ast_root)

    self.assertEqual(len(optimization_analyzer.visit_ast.GetCalls()), 4)


class TestAssignAfterFilterWarning(unittest.TestCase):

  def setUp(self):
    options = analyzer.default_options
    options.update(cache_resolved_placeholders=True,
                   enable_warnings=True, warnings_as_errors=True)
    self.compiler = util.Compiler(
        analyzer_options=options,
        xspt_mode=False)

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
    ast_root = TemplateNode('TestTemplate')
    function_node = FunctionNode('test_function')
    ast_root.append(function_node)
    first_assign = AssignNode(IdentifierNode('foo'), LiteralNode('foo'))
    function_node.append(first_assign)
    first_use = FilterNode(IdentifierNode('foo'))
    function_node.append(first_use)
    second_assign = AssignNode(IdentifierNode('foo'), LiteralNode('bar'))
    function_node.append(second_assign)
    second_use = FilterNode(IdentifierNode('foo'))
    function_node.append(second_use)

    optimization_analyzer = optimizer.OptimizationAnalyzer(
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    optimization_analyzer.visit_ast = unittest.RecordedFunction(
        optimization_analyzer.visit_ast)

    self.assertRaises(util.Warning,
                      optimization_analyzer.visit_ast,
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
    ast_root = TemplateNode('TestTemplate')
    function_node = FunctionNode('test_function')
    ast_root.append(function_node)
    first_assign = AssignNode(IdentifierNode('foo'), LiteralNode('foo'))
    function_node.append(first_assign)
    second_assign = AssignNode(IdentifierNode('foo'), LiteralNode('bar'))
    function_node.append(second_assign)
    first_use = FilterNode(IdentifierNode('foo'))
    function_node.append(first_use)

    optimization_analyzer = optimizer.OptimizationAnalyzer(
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    optimization_analyzer.visit_ast = unittest.RecordedFunction(
        optimization_analyzer.visit_ast)

    try:
      optimization_analyzer.visit_ast(ast_root)
    except util.Warning:
      self.fail('visit_ast raised WarningError unexpectedly.')


class TestPartialLocalIdentifiers(unittest.TestCase):

  def setUp(self):
    options = analyzer.default_options
    options.update(static_analysis=True,
                   directly_access_defined_variables=True)
    self.compiler = util.Compiler(
        analyzer_options=options,
        xspt_mode=False)

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
    ast_root = TemplateNode('TestTemplate')
    function_node = FunctionNode('test_function')
    ast_root.append(function_node)
    if_node = IfNode(LiteralNode(True))
    function_node.append(if_node)
    assign_node = AssignNode(IdentifierNode('foo'), LiteralNode(1))
    if_node.append(assign_node)
    function_node.append(PlaceholderNode('foo'))

    optimization_analyzer = optimizer.OptimizationAnalyzer(
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    optimization_analyzer.visit_ast = unittest.RecordedFunction(
        optimization_analyzer.visit_ast)

    self.assertRaises(analyzer.SemanticAnalyzerError,
                      optimization_analyzer.visit_ast,
                      ast_root)

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
    ast_root = TemplateNode('TestTemplate')
    function_node = FunctionNode('test_function')
    ast_root.append(function_node)
    if_node = IfNode(LiteralNode(True))
    function_node.append(if_node)
    if_node.append(AssignNode(IdentifierNode('foo'), LiteralNode(1)))
    if_node.else_.append(AssignNode(IdentifierNode('bar'), LiteralNode(1)))
    function_node.append(PlaceholderNode('foo'))

    optimization_analyzer = optimizer.OptimizationAnalyzer(
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    optimization_analyzer.visit_ast = unittest.RecordedFunction(
        optimization_analyzer.visit_ast)

    self.assertRaises(analyzer.SemanticAnalyzerError,
                      optimization_analyzer.visit_ast,
                      ast_root)

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
    ast_root = TemplateNode('TestTemplate')
    function_node = FunctionNode('test_function')
    ast_root.append(function_node)
    if_node = IfNode(LiteralNode(True))
    function_node.append(if_node)
    if_node.append(AssignNode(IdentifierNode('foo'), LiteralNode(1)))
    if_node.else_.append(AssignNode(IdentifierNode('bar'), LiteralNode(1)))
    function_node.append(PlaceholderNode('bar'))

    optimization_analyzer = optimizer.OptimizationAnalyzer(
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    optimization_analyzer.visit_ast = unittest.RecordedFunction(
        optimization_analyzer.visit_ast)

    self.assertRaises(analyzer.SemanticAnalyzerError,
                      optimization_analyzer.visit_ast,
                      ast_root)

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
    ast_root = TemplateNode('TestTemplate')
    function_node = FunctionNode('test_function')
    ast_root.append(function_node)
    if_node = IfNode(LiteralNode(True))
    function_node.append(if_node)
    if_node.append(AssignNode(IdentifierNode('foo'), LiteralNode(1)))
    if_node_2 = IfNode(LiteralNode(True))
    if_node_2.append(AssignNode(IdentifierNode('foo'), LiteralNode(2)))
    if_node_2.else_.append(AssignNode(IdentifierNode('foo'), LiteralNode(3)))
    if_node.else_.append(if_node_2)

    function_node.append(PlaceholderNode('foo'))

    optimization_analyzer = optimizer.OptimizationAnalyzer(
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    optimization_analyzer.visit_ast = unittest.RecordedFunction(
        optimization_analyzer.visit_ast)

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
    ast_root = TemplateNode('TestTemplate')
    function_node = FunctionNode('test_function')
    ast_root.append(function_node)
    if_node = IfNode(LiteralNode(True))
    function_node.append(if_node)
    if_node_2 = IfNode(LiteralNode(True))
    if_node_2.append(AssignNode(IdentifierNode('foo'), LiteralNode(1)))
    if_node_2.else_.append(AssignNode(IdentifierNode('foo'), LiteralNode(2)))
    if_node.append(if_node_2)
    if_node.else_.append(AssignNode(IdentifierNode('foo'), LiteralNode(3)))
    function_node.append(PlaceholderNode('foo'))

    optimization_analyzer = optimizer.OptimizationAnalyzer(
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    optimization_analyzer.visit_ast = unittest.RecordedFunction(
        optimization_analyzer.visit_ast)

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
    ast_root = TemplateNode('TestTemplate')
    function_node = FunctionNode('test_function')
    ast_root.append(function_node)
    if_node = IfNode(LiteralNode(True))
    function_node.append(if_node)
    if_node_2 = IfNode(LiteralNode(True))
    if_node_2.append(AssignNode(IdentifierNode('foo'), LiteralNode(1)))
    if_node_2.else_.append(AssignNode(IdentifierNode('bar'), LiteralNode(2)))
    if_node.append(if_node_2)
    if_node.else_.append(AssignNode(IdentifierNode('foo'), LiteralNode(3)))
    function_node.append(PlaceholderNode('foo'))

    optimization_analyzer = optimizer.OptimizationAnalyzer(
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    optimization_analyzer.visit_ast = unittest.RecordedFunction(
        optimization_analyzer.visit_ast)

    self.assertRaises(analyzer.SemanticAnalyzerError,
                      optimization_analyzer.visit_ast,
                      ast_root)

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
    ast_root = TemplateNode('TestTemplate')
    function_node = FunctionNode('test_function')
    ast_root.append(function_node)
    if_node = IfNode(LiteralNode(True))
    function_node.append(if_node)
    if_node.append(AssignNode(IdentifierNode('foo'), LiteralNode(1)))
    if_node_2 = IfNode(LiteralNode(True))
    if_node_2.append(AssignNode(IdentifierNode('bar'), LiteralNode(2)))
    if_node_2.else_.append(AssignNode(IdentifierNode('baz'), LiteralNode(3)))
    if_node.else_.append(if_node_2)
    function_node.append(PlaceholderNode('baz'))

    optimization_analyzer = optimizer.OptimizationAnalyzer(
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    optimization_analyzer.visit_ast = unittest.RecordedFunction(
        optimization_analyzer.visit_ast)

    self.assertRaises(analyzer.SemanticAnalyzerError,
                      optimization_analyzer.visit_ast,
                      ast_root)

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
    ast_root = TemplateNode('TestTemplate')
    function_node = FunctionNode('test_function')
    ast_root.append(function_node)
    if_node = IfNode(LiteralNode(True))
    function_node.append(if_node)
    if_node.append(AssignNode(IdentifierNode('foo'), LiteralNode(1)))
    if_node_2 = IfNode(LiteralNode(True))
    if_node_2.append(AssignNode(IdentifierNode('foo'), LiteralNode(2)))
    if_node.else_.append(if_node_2)
    function_node.append(PlaceholderNode('foo'))

    optimization_analyzer = optimizer.OptimizationAnalyzer(
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    optimization_analyzer.visit_ast = unittest.RecordedFunction(
        optimization_analyzer.visit_ast)

    self.assertRaises(analyzer.SemanticAnalyzerError,
                      optimization_analyzer.visit_ast,
                      ast_root)

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
    ast_root = TemplateNode('TestTemplate')
    function_node = FunctionNode('test_function')
    ast_root.append(function_node)
    if_node = IfNode(LiteralNode(True))
    function_node.append(if_node)
    if_node.append(AssignNode(IdentifierNode('foo'), LiteralNode(1)))
    if_node_2 = IfNode(LiteralNode(True))
    if_node_2.append(AssignNode(IdentifierNode('foo'), LiteralNode(2)))
    if_node_2.else_.append(AssignNode(IdentifierNode('foo'), LiteralNode(3)))
    if_node.else_.append(if_node_2)
    function_node.append(PlaceholderNode('foo'))

    optimization_analyzer = optimizer.OptimizationAnalyzer(
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    optimization_analyzer.visit_ast = unittest.RecordedFunction(
        optimization_analyzer.visit_ast)

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
    ast_root = TemplateNode('TestTemplate')
    function_node = FunctionNode('test_function')
    ast_root.append(function_node)
    if_node = IfNode(LiteralNode(True))
    function_node.append(if_node)
    if_node.append(AssignNode(IdentifierNode('foo'), LiteralNode(1)))
    if_node_2 = IfNode(LiteralNode(True))
    if_node_2.append(PlaceholderNode('foo'))
    function_node.append(if_node_2)

    optimization_analyzer = optimizer.OptimizationAnalyzer(
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    optimization_analyzer.visit_ast = unittest.RecordedFunction(
        optimization_analyzer.visit_ast)

    self.assertRaises(analyzer.SemanticAnalyzerError,
                      optimization_analyzer.visit_ast,
                      ast_root)


if __name__ == '__main__':
  unittest.main()
