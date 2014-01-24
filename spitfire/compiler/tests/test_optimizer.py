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


if __name__ == '__main__':
  unittest.main()
