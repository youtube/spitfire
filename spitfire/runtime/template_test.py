# Copyright 2015 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import sys
import unittest

from spitfire.runtime import filters
from spitfire.runtime import template
from spitfire.runtime import baked
try:
    from spitfire.runtime import _template  # pylint: disable=g-import-not-at-top
except ImportError:
    _template = None


@filters.skip_filter
def is_skip():
    pass


def no_skip():
    pass

# Do not inherit from unittest.TestCase to ensure that these tests don't run.
# Add tests here and they will be run for the C and Python implementations. This
# should make sure that both implementations are equivalent.
class _TestTemplate(object):

    template_cls = None

    def setUp(self):
        self.template = self.template_cls()
        self.template._filter_function = lambda v: 'FILTERED'

    def test_skip_filter(self):
        self.assertEqual(self.template.filter_function('foo', is_skip), 'foo')

    def test_skip_filter_builtin(self):
        # Ensure skip_filter works for built-in functions as well,
        # choice of getdefaultencoding is abitrary - it's a built-in function
        is_skip_builtin = filters.skip_filter(sys.getdefaultencoding)
        self.assertEqual(self.template.filter_function('foo', is_skip_builtin),
                         'foo')
        # Ensure wrapped function works as expected
        self.assertEqual(is_skip_builtin(), sys.getdefaultencoding())

    def test_no_skip(self):
        self.assertEqual(
            self.template.filter_function('foo', no_skip), 'FILTERED')

    def test_str(self):
        self.assertEqual(self.template.filter_function('foo'), 'FILTERED')

    def test_sanitized(self):
        got = self.template.filter_function(baked.SanitizedPlaceholder('foo'))
        want = baked.SanitizedPlaceholder('foo')
        self.assertEqual(got, want)
        self.assertEqual(type(got), type(want))


class TestTemplatePy(_TestTemplate, unittest.TestCase):
    template_cls = template.get_spitfire_template_class(
        prefer_c_extension=False)


if _template is not None:

    class TestTemplateC(_TestTemplate, unittest.TestCase):
        template_cls = template.get_spitfire_template_class(
            prefer_c_extension=True)


if __name__ == '__main__':
    unittest.main()
