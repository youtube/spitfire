import unittest
from spitfire.runtime import udn

class Scope(object):
  boom = 'bam'

class Foo(object):
  bar = 'baz'
  search_list = [
    {'win': 'boo'},
    Scope(),
  ]
  placeholder_cache = None


class TestResolvePlaceholder(unittest.TestCase):

  def test_has_attr(self):
    self.assertEqual(udn.resolve_placeholder('bar', Foo, None), 'baz')

  def test_in_search_list_dict(self):
    self.assertEqual(udn.resolve_placeholder('win', Foo, None), 'boo')

  def test_in_search_list_object(self):
    self.assertEqual(udn.resolve_placeholder('boom', Foo, None), 'bam')

  def test_in_globals(self):
    self.assertEqual(udn.resolve_placeholder('blam', Foo, {'blam': 'bling'}), 'bling')

  def test_builtin(self):
    self.assertEqual(udn.resolve_placeholder('str', Foo, None), str)

  def test_undefined(self):
    self.assertEqual(type(udn.resolve_placeholder('wowza', Foo, None)),
                     udn.UndefinedPlaceholder)


class TestResolvePlaceholderWithCache(unittest.TestCase):

  def test_in_search_list_dict(self):
    template = Foo()
    template.placeholder_cache = {}
    self.assertEqual(udn.resolve_placeholder('win', template, None), 'boo')
    self.assertIn('win', template.placeholder_cache)
    self.assertEqual(udn.resolve_placeholder('win', template, None), 'boo')

  def test_in_search_list_object(self):
    template = Foo()
    template.placeholder_cache = {}
    self.assertEqual(udn.resolve_placeholder('boom', template, None), 'bam')
    self.assertIn('boom', template.placeholder_cache)
    self.assertEqual(udn.resolve_placeholder('boom', template, None), 'bam')


class TestResolvePlaceholderWithLocals(unittest.TestCase):

  def test_in_locals(self):
    self.assertEqual(udn.resolve_placeholder_with_locals('foo', Foo,
                                                         {'foo': 'bar'},
                                                         None), 'bar')

if __name__ == '__main__':
  unittest.main()
