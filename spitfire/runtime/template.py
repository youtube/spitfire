# Copyright 2007 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

# an 'abstract' base class for a template, seems like a good idea for now

import cStringIO as StringIO

from spitfire import runtime
from spitfire.runtime import baked
from spitfire.runtime import filters
from spitfire.runtime import udn

try:
    from spitfire.runtime import _template  # pylint: disable=g-import-not-at-top
except ImportError:
    _template = None


# NOTE: in some instances, this is faster than using cStringIO
# this is slightly counter intuitive and probably means there is more here than
# meets the eye.
class BufferIO(list):
    write = list.append

    def getvalue(self):
        return ''.join(self)


class _BaseSpitfireTemplate(object):

    # filter_function checks if the value should be filtered. If it is a
    # SanitizedPlaceholder or the placeholder_function has a skip_filter
    # annotation, there is no need to filter. Otherwise, call
    # self._filter_function.
    def filter_function(self, value, placeholder_function=None):
        """Checks if the value should be filtered.

        If it is a SanitizedPlaceholder or the placeholder_function has
        a skip_filter annotation, there is no need to filter. Otherwise, call
        self._filter_function.

        Args:
          value: The value that may need to be filtered.
          placeholder_function: If present and annotated, do not filter.

        Returns:
          value, filtered if necessary.
        """
        if isinstance(value, baked.SanitizedPlaceholder):
            return value
        elif (placeholder_function is not None and
              getattr(placeholder_function, 'skip_filter', False)):
            return value
        else:
            return self._filter_function(value)


def get_spitfire_template_class(prefer_c_extension=True):
    """Returns an appropriate SpitfireTemplate class.

    Args:
      prefer_c_extension: If set True and _template loaded properly, use the
        C extension's baseclass implementation.

    Returns:
      A SpitfireTemplate class with an appropriate base class.
    """
    if prefer_c_extension and _template is not None:
        baseclass = _template.BaseSpitfireTemplate
    else:
        baseclass = _BaseSpitfireTemplate

    class _SpitfireTemplate(baseclass):
        # store a reference to the filter function - this is tricky because of
        # some python stuff. filter functions look like this:
        #
        # def filter_function(template_instance, value):
        #
        # when this is assigned to a template instance, accessing this name
        # binds the function to the current instance. using the name
        # 'template_instance' to indicate that these functions aren't really
        # related to the template.
        _filter_function = staticmethod(filters.simple_str_filter)
        repeat = None
        placeholder_cache = None

        def __init__(self,
                     search_list=None,
                     default_filter=None,
                     use_placeholder_cache=False):
            # use_placeholder_cache - cache the values returned from the
            # search_list?   The cached values will live for the lifetime of
            # this object.
            self.search_list = search_list
            if use_placeholder_cache:
                self.placeholder_cache = {}
            if default_filter is not None:
                self._filter_function = default_filter

            # FIXME: repeater support is not needed most of the time, just
            # disable it for the time being
            # self.repeat = spitfire.runtime.repeater.RepeatTracker()

        def get_var(self, name, default=None):
            return udn.resolve_from_search_list(self.search_list, name, default)

        def has_var(self, name):
            var = self.get_var(name, default=runtime.UnresolvedPlaceholder)
            return var is not runtime.UnresolvedPlaceholder

        @staticmethod
        def new_buffer():
            return BufferIO()

    return _SpitfireTemplate


SpitfireTemplate = get_spitfire_template_class()


def template_method(function):
    function.template_method = True
    function.skip_filter = True
    return function
