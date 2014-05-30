import unittest
from spitfire.compiler.ast import *
from spitfire.compiler import analyzer
from spitfire.compiler import util


class BaseTest(unittest.TestCase):

  def __init__(self, *args):
    unittest.TestCase.__init__(self, *args)
    self.options = analyzer.default_options
    self.options.update(cache_resolved_placeholders=True,
                        enable_warnings=True, warnings_as_errors=True)

  def setUp(self):
    self.compiler = util.Compiler(
        analyzer_options=self.options,
        xspt_mode=False,
        compiler_stack_traces=True)

  def _get_analyzer(self, ast_root):
    semantic_analyzer = analyzer.SemanticAnalyzer(
        'TestTemplate',
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)
    semantic_analyzer.get_ast = unittest.RecordedFunction(
        semantic_analyzer.get_ast)
    return semantic_analyzer

  def _build_function_template(self):
    """ Build a simple template with a function.

    file: TestTemplate
    #def test_function
    #end def
    """
    ast_root = TemplateNode('TestTemplate')
    def_node = DefNode('test_function')
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
    condition_node = condition or LiteralNode(True)
    if_node = IfNode(condition_node)
    def_node.append(if_node)
    return (ast_root, def_node, if_node)


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
    if_node.append(OptionalWhitespaceNode(' '))

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
    assign_node = AssignNode(IdentifierNode('foo'), LiteralNode(True))
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
    assign_node = AssignNode(IdentifierNode('foo'), LiteralNode(True))
    if_node.append(assign_node)
    elif_node = IfNode(LiteralNode(False))
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
    assign_node = AssignNode(IdentifierNode('foo'), LiteralNode(True))
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
    target_list = TargetListNode()
    target_list.append(PlaceholderNode('foo'))
    expression_list = ExpressionListNode()
    expression_list.append(LiteralNode([]))
    for_node = ForNode(target_list=target_list, expression_list=expression_list)
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
    for_node.append(OptionalWhitespaceNode(' '))

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
    assign_node = AssignNode(IdentifierNode('foo'), LiteralNode(True))
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
    ast_root = TemplateNode('TestTemplate')
    implements_node = ImplementsNode('library')
    ast_root.append(implements_node)
    def_node = DefNode('test_function')
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
    assign_node = AssignNode(IdentifierNode('foo'), LiteralNode(True))
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
    attr_node = AttributeNode('foo', default=LiteralNode(True))
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
    global_node = GlobalNode('foo')
    ast_root.insert_before(def_node, global_node)

    semantic_analyzer = self._get_analyzer(ast_root)

    try:
      semantic_analyzer.get_ast()
    except analyzer.SemanticAnalyzerError:
      self.fail('get_ast raised SemanticAnalyzerError unexpectedly.')


if __name__ == '__main__':
  unittest.main()
