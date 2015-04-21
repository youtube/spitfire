import unittest
from spitfire.runtime import _baked
from spitfire.runtime import baked


def is_skip():
  pass
is_skip.skip_filter = True


def no_skip():
  pass


# Do not inherit from unittest.TestCase to ensure that these tests don't run.
# Add tests here and they will be run for the C and Python implementations. This
# should make sure that both implementations are equivalent.
class _BakedTest(object):

  module = None

  def setUp(self):
    self.SanitizedPlaceholder = self.module._SanitizedPlaceholder
    self.mark_as_sanitized = self.module._mark_as_sanitized
    self.runtime_mark_as_sanitized = self.module._runtime_mark_as_sanitized

  def test_make_sanitized_placeholder(self):
    self.assertEqual(str(self.SanitizedPlaceholder('bar')), 'bar')

  def test_type_sanitized_placeholder(self):
    self.assertEqual(type(self.SanitizedPlaceholder('bar')),
                     self.SanitizedPlaceholder)

  def test_sanitize_number(self):
    self.assertEqual(self.mark_as_sanitized(1), 1)

  def test_sanitize_string(self):
    v = self.mark_as_sanitized('foo')
    self.assertEqual(v, self.SanitizedPlaceholder('foo'))
    self.assertEqual(type(v), self.SanitizedPlaceholder)

  def test_runtime_sanitize_false(self):
    v = self.runtime_mark_as_sanitized('foo', no_skip)
    self.assertEqual(v, 'foo')
    self.assertEqual(type(v), str)

  def test_runtime_sanitize_true_not_string(self):
    v = self.runtime_mark_as_sanitized(1, is_skip)
    self.assertEqual(v, 1)

  def test_runtime_sanitize_true(self):
    v = self.runtime_mark_as_sanitized('foo', is_skip)
    self.assertEqual(v, 'foo')
    self.assertEqual(type(v), self.SanitizedPlaceholder)

  def test_add_sanitized(self):
    a = self.SanitizedPlaceholder('foo')
    b = self.SanitizedPlaceholder('bar')
    v = a + b
    self.assertEqual(v, 'foobar')
    self.assertEqual(type(v), self.SanitizedPlaceholder)

  def test_add_not_sanitized(self):
    a = self.SanitizedPlaceholder('foo')
    b = 'bar'
    v = a + b
    self.assertEqual(v, 'foobar')
    self.assertEqual(type(v), str)

  def test_add_reverse_not_sanitized(self):
    a = self.SanitizedPlaceholder('foo')
    b = 'bar'
    v = b + a
    self.assertEqual(v, 'barfoo')
    self.assertEqual(type(v), str)

  def test_mod_sanitized(self):
    a = self.SanitizedPlaceholder('foo%s')
    b = self.SanitizedPlaceholder('bar')
    v = a % b
    self.assertEqual(v, 'foobar')
    self.assertEqual(type(v), self.SanitizedPlaceholder)

  def test_mod_not_sanitized(self):
    a = self.SanitizedPlaceholder('foo%s')
    b = 'bar'
    v = a % b
    self.assertEqual(v, 'foobar')
    self.assertEqual(type(v), str)

  def test_mod_dict_not_sanitized(self):
    a = self.SanitizedPlaceholder('foo%(b)s')
    b = 'bar'
    v = a % vars()
    self.assertEqual(v, 'foobar')
    self.assertEqual(type(v), str)


class TestBakedPy(_BakedTest, unittest.TestCase):
  module = baked


class TestBakedC(_BakedTest, unittest.TestCase):
  module = _baked


if __name__ == '__main__':
  unittest.main()
