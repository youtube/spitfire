# Copyright 2008 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

# a few helpful filter functions

import functools
import types
from spitfire import runtime
from spitfire.runtime import udn


# decorate a function object so the default filter will not be applied to the
# value of a placeholder. this is handy when building functions that will
# create data that could be double-escaped and you don't wnat to constantly
# inform spitfire to us raw mode.
def skip_filter(function):
    if isinstance(function, types.BuiltinFunctionType):
        # Built-in functions don't allow abitrary attributes, so we use a
        # wrapper function that just passes through
        @functools.wraps(function)
        def skip_filter_wrapper(*args, **kwargs):
            return function(*args, **kwargs)
        skip_filter_wrapper.skip_filter = True
        return skip_filter_wrapper

    function.skip_filter = True
    return function


def passthrough_filter(value):
    return value


@skip_filter
def escape_html(value, quote=True):
    """Replace special characters '&', '<' and '>' by SGML entities."""
    value = simple_str_filter(value)
    if isinstance(value, basestring):
        value = value.replace("&", "&amp;")  # Must be done first!
        value = value.replace("<", "&lt;")
        value = value.replace(">", "&gt;")
        if quote:
            value = value.replace('"', "&quot;")
    return value


# deprecated
def safe_values(value):
    """Deprecated - use simple_str_filter instead."""
    if isinstance(value, (str, unicode, int, long, float,
                          runtime.UndefinedPlaceholder)):
        return value
    else:
        return ''


def simple_str_filter(value):
    """Return a string if the input type is something primitive."""
    if isinstance(value, (str, unicode, int, long, float,
                          runtime.UndefinedPlaceholder)):
        # fixme: why do force this conversion here?
        # do we want to be unicode or str?
        return str(value)
    else:
        return ''


# test function for function registry - don't use
@skip_filter
def escape_html_function(value):
    return escape_html(value)
