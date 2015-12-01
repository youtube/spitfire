import unittest
from spitfire.runtime import _udn
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


class Baz(object):
  bar = 'win'


class _UdnTest(object):

  resolve_udn = None

  def testResolveHitWithoutException(self):
    self.assertEqual(self.resolve_udn(Baz(), 'bar'), 'win')

  def testResolveHitWithException(self):
    self.assertEqual(self.resolve_udn(Baz(), 'bar', raise_exception=True),
                     'win')

  def testResolveMissWithoutException(self):
    self.assertIsInstance(self.resolve_udn(Baz(), 'missing'),
                          udn.UndefinedAttribute)

  def testResolveDoubleMissWithoutException(self):
    """Shows that it's UndefinedAttribute's all the way down."""
    undefined_attr = self.resolve_udn(Baz(), 'missing')
    self.assertIsInstance(undefined_attr, udn.UndefinedAttribute)
    undefined_attr2 = self.resolve_udn(undefined_attr, 'missing')
    self.assertIsInstance(undefined_attr2, udn.UndefinedAttribute)

  def testResolveMissWithException(self):
    self.assertRaises(udn.UDNResolveError, self.resolve_udn, Baz(), 'misssing',
                      raise_exception=True)


class TestUdnC(_UdnTest, unittest.TestCase):
  resolve_udn = staticmethod(_udn._resolve_udn)


class TestUdnPyAttr3(_UdnTest, unittest.TestCase):
  resolve_udn = staticmethod(udn.resolve_udn_prefer_attr3)


class TestUdnPyAttr2(_UdnTest, unittest.TestCase):
  resolve_udn = staticmethod(udn.resolve_udn_prefer_attr2)


class TestUdnPyAttr(_UdnTest, unittest.TestCase):
  resolve_udn = staticmethod(udn.resolve_udn_prefer_attr)


class TestUdnPyDict(_UdnTest, unittest.TestCase):
  resolve_udn = staticmethod(udn.resolve_udn_prefer_dict)


if __name__ == '__main__':
  unittest.main()
