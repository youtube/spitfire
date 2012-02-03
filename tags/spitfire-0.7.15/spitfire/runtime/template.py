# an 'abstract' base class for a template, seems like a good idea for now

#import StringIO
import cStringIO as StringIO
import spitfire.runtime.filters
import spitfire.runtime.repeater

from spitfire.runtime.udn import (
  _resolve_from_search_list, UnresolvedPlaceholder)


# NOTE: in some instances, this is faster than using cStringIO
# this is slightly counter intuitive and probably means there is more here than
# meets the eye. 
class BufferIO(list):
  write = list.append

  def getvalue(self):
    return ''.join(self)


class SpitfireTemplate(object):
  # store a reference to the filter function - this is tricky because of some
  # python stuff. filter functions look like this:
  #
  # def filter_function(template_instance, value):
  #
  # when this is assigned to a template instance, accessing this name binds the
  # function to the current instance. using the name 'template_instance' to
  # indicate that these functions aren't really related to the template.
  _filter_function = staticmethod(spitfire.runtime.filters.simple_str_filter)
  repeat = None
  
  def __init__(self, search_list=None, default_filter=None):
    self.search_list = search_list
    if default_filter is not None:
      self._filter_function = default_filter

    # FIXME: repeater support is not needed most of the time, just
    # disable it for the time being
    # self.repeat = spitfire.runtime.repeater.RepeatTracker()
    
  def get_var(self, name, default=None):
    return _resolve_from_search_list(self.search_list, name, default)

  def has_var(self, name):
    var = self.get_var(name, default=UnresolvedPlaceholder) 
    return var is not UnresolvedPlaceholder

  # wrap the underlying filter call so that items don't get filtered multiple
  # times (avoids double escaping)
  # fixme: this could be a hotspot, having to call getattr all the time seems
  # like it might be a bit pokey
  def filter_function(self, value, placeholder_function=None):
    #print "filter_function", placeholder_function, self._filter_function, "value: '%s'" % value
    if (placeholder_function is not None and
        getattr(placeholder_function, 'skip_filter', False)):
      return value
    else:
      value = self._filter_function(value)
      return value
    
  @staticmethod
  def new_buffer():
    return BufferIO()


def enable_psyco(template_class):
  import psyco
  psyco.bind(SpitfireTemplate)
  psyco.bind(template_class)

def template_method(function):
  function.template_method = True
  function.skip_filter = True
  return function
