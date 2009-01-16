# resolve unified-dotted-notation and placeholders
# this means search objects and dictionaries in the same way
# using attribute-like syntax from python
# syntactically, 'name' will always be a valid identifier - so you won't get
# name='my attribute' - it must be a legal python identifier

import __builtin__
import inspect

# create a sentinel value for missing attributes
class __MissingAttr(object):
  pass
MissingAttr = __MissingAttr()

# sentinel class, in case you want to have a default that is None
class __Unspecified(object):
  pass
Unspecified = __Unspecified()

# the idea is to have something that is always like None, but explodes when
# you try to use it as a string. this means that you can resolve placeholders
# and evaluate them in complex conditional expressions, allowing them to be
# hoisted, and still protect conditional access to the values
# it could also be that you might try to call the result - in that case, blow
# and exception as well.
class UndefinedPlaceholder(object):
  def __init__(self, name, available_placeholders):
    self.name = name
    self.available_placeholders = available_placeholders

  def __nonzero__(self):
    return False

  def __str__(self):
    raise PlaceholderError(self.name, self.available_placeholders)

  def __call__(self, *pargs, **kargs):
    raise PlaceholderError(self.name, self.available_placeholders)

class __UnresolvedPlaceholder(object):
  pass
UnresolvedPlaceholder = __UnresolvedPlaceholder()

# Cheetah supports autocalling - Spitfire does not. this stand-in class will
# raise an exception if you do something like compare a function object.
class CallOnlyPlaceholder(object):
  def __init__(self, name, function):
    self.name = name
    self.function = function
    
  def __call__(self, *pargs, **kargs):
    return self.function(*pargs, **kargs)

  @property
  def template_method(self):
    return getattr(self.function, 'template_method')

  @property
  def skip_filter(self):
    return getattr(self.function, 'skip_filter')
  
  def __cmp__(self):
    raise PlaceholderError(self.name, 'function placeholder was not called')

  def __nonzero__(self):
    raise PlaceholderError(self.name, 'function placeholder was not called')

class PlaceholderError(KeyError):
  pass

class UDNResolveError(Exception):
  pass


# TODO - optimize performance
def resolve_udn_prefer_attr(_object, name):
  try:
    return getattr(_object, name)
  except AttributeError:
    try:
      return _object[name]
    except (KeyError, TypeError):
      raise UDNResolveError(name, dir(_object))

def resolve_udn_prefer_dict(_object, name):
  try:
    return _object[name]
  except (KeyError, TypeError):
    try:
      return getattr(_object, name)
    except AttributeError:
      raise UDNResolveError(name, dir(_object))

# this is always faster than catching an exception when that exception isn't
# truly exceptional,  but semi-expected
# using a sentinel should be quicker than calling hasattr then getattr
# this is true when the expected hit rate on an attribute is relatively
# reasonable - say 50% chance
def resolve_udn_prefer_attr2(_object, name):
  val = getattr(_object, name, MissingAttr)
  if val is not MissingAttr:
    return val
  try:
    return _object[name]
  except (KeyError, TypeError):
    raise UDNResolveError(name, dir(_object))

# this version is slightly faster when there are a lot of misses on attributes
def resolve_udn_prefer_attr3(_object, name):
  if hasattr(_object, name):
    return getattr(_object, name)
  try:
    return _object[name]
  except (KeyError, TypeError):
    raise UDNResolveError(name, dir(_object))

# FIXME: i'm sure this is a little pokey - might be able to speed this up
# somehow. not sure if it's better to look before leaping or raise.
# might also want to let users tune whether to prefer keys or attributes
def _resolve_placeholder(name, template=None, local_vars=None, global_vars=None,
                        default=Unspecified):
  if local_vars is not None:
    try:
      return local_vars[name]
    except TypeError:
      raise PlaceholderError('unexpected type for local_vars: %s' %
                             type(local_vars))
    except KeyError:
      pass

  if template is not None:
    try:
      return getattr(template, name)
    except AttributeError:
      pass

  if template.search_list is not None:
    ph = get_var_from_search_list(name, template.search_list)
    if ph is not UnresolvedPlaceholder:
      return ph

  if global_vars is not None:
    try:
      return global_vars[name]
    except TypeError:
      raise PlaceholderError('unexpected type for global_vars: %s' %
                             type(global_vars))
    except KeyError:
      pass

  # fixme: finally try to resolve builtins - this should be configurable
  # if you compile optimized modes, this isn't necessary
  default = getattr(__builtin__, name, default)

  if default is not Unspecified:
    return default
  else:
    return UndefinedPlaceholder(name,
                                [get_available_placeholders(scope)
                                 for scope in template.search_list])
#     raise PlaceholderError(name,
#                            [get_available_placeholders(scope)
#                             for scope in template.search_list])


def _debug_resolve_placeholder(name, *pargs, **kargs):
  placeholder = _resolve_placeholder(name, *pargs, **kargs)
  if inspect.isroutine(placeholder):
    return CallOnlyPlaceholder(name, placeholder)
  else:
    return placeholder

def _debug_resolve_udn(_object, name, *pargs, **kargs):
  placeholder = resolve_udn_prefer_attr3(_object, name, *pargs, **kargs)
  if inspect.isroutine(placeholder):
    return CallOnlyPlaceholder(name, placeholder)
  else:
    return placeholder

resolve_placeholder = _resolve_placeholder

def get_var_from_search_list(name, search_list):
  for scope in search_list:
    try:
      return scope[name]
    except (TypeError, KeyError):
      pass

    try:
      return getattr(scope, name)
    except AttributeError:
      pass
  return UnresolvedPlaceholder


def get_available_placeholders(scope):
  if isinstance(scope, dict):
    return scope.keys()
  else:
    return dir(scope)


resolve_udn = resolve_udn_prefer_attr3
