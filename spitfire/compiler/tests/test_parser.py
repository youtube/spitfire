import unittest
from spitfire.compiler.ast import *
from spitfire.compiler import util


class BaseTest(unittest.TestCase):

  def _compile(self, template_content):
    template_node = util.parse_template(template_content)
    template_node.source_path = 'test_template.spt'
    return template_node

  def _find_node(self, ast, pred):
    """Look for a given node based on a predicate function.
    Return the first one found"""
    if pred(ast):
      return ast
    for child_node in ast.child_nodes:
      found = self._find_node(child_node, pred)
      if found:
        return found
      if isinstance(ast, (CallFunctionNode, FilterNode)):
        found = self._find_node(ast.expression, pred)
        if found:
          return found
    return None


class TestEscapeHash(BaseTest):

  def test_escape_simple(self):
    code = """
#def foo
\#test
#end def
    """
    template = self._compile(code)
    def pred(node):
      return bool(type(node) == DefNode and
                  node.name == 'foo')

    def_node = self._find_node(template, pred)
    text = ''.join([node.value for node in def_node.child_nodes if type(node) == TextNode])
    self.assertEqual(text, '#test')


  def test_backslash_hash_escape(self):
    code = """
#def foo
\\\#test
#end def
    """
    template = self._compile(code)
    def pred(node):
      return bool(type(node) == DefNode and
                  node.name == 'foo')

    def_node = self._find_node(template, pred)
    text = ''.join([node.value for node in def_node.child_nodes if type(node) == TextNode])
    self.assertEqual(text, '\\#test')

  def test_escape_needed(self):
    code = """
#def foo
\#if
#end def
    """
    template = self._compile(code)
    def pred(node):
      return bool(type(node) == DefNode and
                  node.name == 'foo')

    def_node = self._find_node(template, pred)
    text = ''.join([node.value for node in def_node.child_nodes if type(node) == TextNode])
    self.assertEqual(text, '#if')


if __name__ == '__main__':
  unittest.main()
