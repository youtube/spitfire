import unittest
from spitfire.compiler.ast import *
from spitfire.compiler import analyzer
from spitfire.compiler import util


class TestEmptyIfBlockError(unittest.TestCase):

  def setUp(self):
    options = analyzer.default_options
    options.update(cache_resolved_placeholders=True,
                   enable_warnings=True, warnings_as_errors=True)
    self.compiler = util.Compiler(
        analyzer_options=options,
        xspt_mode=False,
        compiler_stack_traces=True)

  def test_empty_if_fails(self):
    self.ast_description = """
    file: TestTemplate
    #def test_function
      #if True
      #end if
    #end def
    """
    ast_root = TemplateNode('TestTemplate')
    def_node = DefNode('test_function')
    ast_root.append(def_node)
    if_node = IfNode(LiteralNode(True))
    def_node.append(if_node)

    semantic_analyzer = analyzer.SemanticAnalyzer(
        'TestTemplate',
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    semantic_analyzer.get_ast = unittest.RecordedFunction(
        semantic_analyzer.get_ast)

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
    ast_root = TemplateNode('TestTemplate')
    def_node = DefNode('test_function')
    ast_root.append(def_node)
    if_node = IfNode(LiteralNode(True))
    if_node.append(OptionalWhitespaceNode(' '))
    def_node.append(if_node)

    semantic_analyzer = analyzer.SemanticAnalyzer(
        'TestTemplate',
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    semantic_analyzer.get_ast = unittest.RecordedFunction(
        semantic_analyzer.get_ast)

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
    ast_root = TemplateNode('TestTemplate')
    def_node = DefNode('test_function')
    ast_root.append(def_node)
    if_node = IfNode(LiteralNode(True))
    def_node.append(if_node)
    assign_node = AssignNode(IdentifierNode('foo'), LiteralNode(True))
    if_node.else_.append(assign_node)

    semantic_analyzer = analyzer.SemanticAnalyzer(
        'TestTemplate',
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    semantic_analyzer.get_ast = unittest.RecordedFunction(
        semantic_analyzer.get_ast)

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
    ast_root = TemplateNode('TestTemplate')
    def_node = DefNode('test_function')
    ast_root.append(def_node)
    if_node = IfNode(LiteralNode(True))
    assign_node = AssignNode(IdentifierNode('foo'), LiteralNode(True))
    if_node.append(assign_node)
    elif_node = IfNode(LiteralNode(False))
    if_node.else_.append(elif_node)
    def_node.append(if_node)

    semantic_analyzer = analyzer.SemanticAnalyzer(
        'TestTemplate',
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    semantic_analyzer.get_ast = unittest.RecordedFunction(
        semantic_analyzer.get_ast)

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
    ast_root = TemplateNode('TestTemplate')
    def_node = DefNode('test_function')
    ast_root.append(def_node)
    if_node = IfNode(LiteralNode(True))
    def_node.append(if_node)
    assign_node = AssignNode(IdentifierNode('foo'), LiteralNode(True))
    if_node.append(assign_node)

    semantic_analyzer = analyzer.SemanticAnalyzer(
        'TestTemplate',
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    semantic_analyzer.get_ast = unittest.RecordedFunction(
        semantic_analyzer.get_ast)

    try:
      semantic_analyzer.get_ast()
    except analyzer.SemanticAnalyzerError:
      self.fail('get_ast raised SemanticAnalyzerError unexpectedly.')


class TestEmptyForBlockError(unittest.TestCase):

  def setUp(self):
    options = analyzer.default_options
    options.update(cache_resolved_placeholders=True,
                   enable_warnings=True, warnings_as_errors=True)
    self.compiler = util.Compiler(
        analyzer_options=options,
        xspt_mode=False,
        compiler_stack_traces=True)

  def test_empty_for_fails(self):
    self.ast_description = """
    file: TestTemplate
    #def test_function
      #for $i in []
      #end for
    #end def
    """
    ast_root = TemplateNode('TestTemplate')
    def_node = DefNode('test_function')
    ast_root.append(def_node)
    target_list = TargetListNode()
    target_list.append(PlaceholderNode('foo'))
    expression_list = ExpressionListNode()
    expression_list.append(LiteralNode([]))
    for_node = ForNode(target_list=target_list, expression_list=expression_list)
    def_node.append(for_node)

    semantic_analyzer = analyzer.SemanticAnalyzer(
        'TestTemplate',
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    semantic_analyzer.get_ast = unittest.RecordedFunction(
        semantic_analyzer.get_ast)

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
    ast_root = TemplateNode('TestTemplate')
    def_node = DefNode('test_function')
    ast_root.append(def_node)
    target_list = TargetListNode()
    target_list.append(PlaceholderNode('foo'))
    expression_list = ExpressionListNode()
    expression_list.append(LiteralNode([]))
    for_node = ForNode(target_list=target_list, expression_list=expression_list)
    for_node.append(OptionalWhitespaceNode(' '))
    def_node.append(for_node)

    semantic_analyzer = analyzer.SemanticAnalyzer(
        'TestTemplate',
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    semantic_analyzer.get_ast = unittest.RecordedFunction(
        semantic_analyzer.get_ast)

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
    ast_root = TemplateNode('TestTemplate')
    def_node = DefNode('test_function')
    ast_root.append(def_node)
    target_list = TargetListNode()
    target_list.append(PlaceholderNode('foo'))
    expression_list = ExpressionListNode()
    expression_list.append(LiteralNode([]))
    for_node = ForNode(target_list=target_list, expression_list=expression_list)
    assign_node = AssignNode(IdentifierNode('foo'), LiteralNode(True))
    for_node.append(assign_node)
    def_node.append(for_node)

    semantic_analyzer = analyzer.SemanticAnalyzer(
        'TestTemplate',
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    semantic_analyzer.get_ast = unittest.RecordedFunction(
        semantic_analyzer.get_ast)

    try:
      semantic_analyzer.get_ast()
    except analyzer.SemanticAnalyzerError:
      self.fail('get_ast raised SemanticAnalyzerError unexpectedly.')


if __name__ == '__main__':
  unittest.main()
