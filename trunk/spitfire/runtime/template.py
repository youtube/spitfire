# an 'abstract' base class for a template, seems like a good idea for now

#import StringIO
import cStringIO as StringIO
import spitfire.runtime.repeater
import spitfire.runtime.filters

# sentinel class, in case you want to have a default that is None
class __Unspecified(object):
  pass
Unspecified = __Unspecified()


class PlaceholderError(KeyError):
  pass


class SpitfireTemplate(object):
  # store a reference to the filter function - this is tricky because of some
  # python stuff. filter functions look like this:
  #
  # def filter_function(template_instance, value):
  #
  # when this is assigned to a template instance, accessing this name binds the
  # function to the current instance. using the name 'template_instance' to
  # indicate that these functions aren't really related to the template.
  _filter_function = spitfire.runtime.filters.safe_values
  
  def __init__(self, search_list=None, default_filter=None):
    self.search_list = search_list
    self.repeat = spitfire.runtime.repeater.RepeatTracker()
    if default_filter is not None:
      self._filter_function = default_filter
    
  # FIXME: i'm sure this is a little pokey - might be able to speed this up
  # somehow. not sure if it's better to look before leaping or raise.
  # might also want to let users tune whether to prefer keys or attributes
  def resolve_placeholder(self, name, local_vars=None, global_vars=None,
                          default=Unspecified):
    if local_vars is not None:
      try:
        return local_vars[name]
      except TypeError:
        raise PlaceholderError('unexpected type for local_vars: %s' %
                               type(local_vars))
      except KeyError:
        pass

    if global_vars is not None:
      try:
        return global_vars[name]
      except TypeError:
        raise PlaceholderError('unexpected type for global_vars: %s' %
                               type(global_vars))
      except KeyError:
        pass

    try:
      return getattr(self, name)
    except AttributeError:
      pass

    if self.search_list is not None:
      for scope in self.search_list:
        try:
          return scope[name]
#           raise PlaceholderError('unexpected type: %s %s' %
#                                  (type(scope), vars(scope)))
        except (TypeError, KeyError):
          pass
        
        try:
          return getattr(scope, name)
        except AttributeError:
          pass

    if default is not Unspecified:
      return default
    else:
      raise PlaceholderError(name,
                             [get_available_placeholders(scope)
                              for scope in self.search_list])

  # fixme: this function seems kind of like a mess, arg ordering etc
  def get_var(self, name, default=Unspecified, local_vars=None,
              global_vars=None):
    return self.resolve_placeholder(name, local_vars=local_vars,
                                    global_vars=global_vars,
                                    default=default)

  def has_var(self, name, local_vars=None, global_vars=None):
    if local_vars is not None and name in local_vars:
      return True
    if global_vars is not None and name in global_vars:
      return True

    if hasattr(self, name):
      return True

    if self.search_list is not None:
      for scope in self.search_list:
        if name in scope:
          return True
        if hasattr(scope, name):
          return True
    return False

  # wrap the underlying filter call so that items don't get filtered multiple
  # times (avoids double escaping)
  # fixme: this could be a hotspot, having to call getattr all the time seems
  # like it might be a bit pokey
  def filter_function(self, value, placeholder_function=None):
    #print "filter_function", placeholder_function, self._filter_function, "value: '%s'" % value
    if (placeholder_function is not None and
        getattr(placeholder_function, 'template_method', False)):
      return value
    else:
      value = self._filter_function(value)
      return value
    
  @staticmethod
  def new_buffer():
    return StringIO.StringIO()

def get_available_placeholders(scope):
  if isinstance(scope, dict):
    return scope.keys()
  else:
    return dir(scope)

def enable_psyco(template_class):
  import psyco
  psyco.bind(SpitfireTemplate)
  psyco.bind(template_class)

def template_method(function):
  function.template_method = True
  return function
