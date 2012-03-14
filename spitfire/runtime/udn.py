# resolve unified-dotted-notation and placeholders
# this means search objects and dictionaries in the same way
# using attribute-like syntax from python
# syntactically, 'name' will always be a valid identifier - so you won't get
# name='my attribute' - it must be a legal python identifier

import __builtin__
import inspect
import logging

from spitfire.runtime import (
  PlaceholderError, UDNResolveError, UnresolvedPlaceholder, 
  UndefinedPlaceholder, UndefinedAttribute)

# create a sentinel value for missing attributes
class __MissingAttr(object):
  pass
MissingAttr = __MissingAttr()

# sentinel class, in case you want to have a default that is None
class __Unspecified(object):
  pass
Unspecified = __Unspecified()

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


# TODO - optimize performance
def resolve_udn_prefer_attr(_object, name, raise_exception=False):
  try:
    return getattr(_object, name)
  except AttributeError:
    try:
      return _object[name]
    except (KeyError, TypeError):
      if raise_exception:
        raise UDNResolveError(name, dir(_object))
      else:
        return UndefinedAttribute(name, dir(_object))

def resolve_udn_prefer_dict(_object, name, raise_exception=False):
  try:
    return _object[name]
  except (KeyError, TypeError):
    try:
      return getattr(_object, name)
    except AttributeError:
      if raise_exception:
        raise UDNResolveError(name, dir(_object))
      else:
        return UndefinedAttribute(name, dir(_object))

# this is always faster than catching an exception when that exception isn't
# truly exceptional,  but semi-expected
# using a sentinel should be quicker than calling hasattr then getattr
# this is true when the expected hit rate on an attribute is relatively
# reasonable - say 50% chance
def resolve_udn_prefer_attr2(_object, name, raise_exception=False):
  val = getattr(_object, name, MissingAttr)
  if val is not MissingAttr:
    return val
  try:
    return _object[name]
  except (KeyError, TypeError):
    if raise_exception:
      raise UDNResolveError(name, dir(_object))
    else:
      return UndefinedAttribute(name, dir(_object))

# this version is slightly faster when there are a lot of misses on attributes
def resolve_udn_prefer_attr3(_object, name, raise_exception=False):
  if hasattr(_object, name):
    return getattr(_object, name)
  try:
    return _object[name]
  except (KeyError, TypeError):
    if raise_exception:
      raise UDNResolveError(name, dir(_object))
    else:
      return UndefinedAttribute(name, dir(_object))

_resolve_udn = resolve_udn_prefer_attr3


# FIXME: i'm sure this is a little pokey - might be able to speed this up
# somehow. not sure if it's better to look before leaping or raise.
# might also want to let users tune whether to prefer keys or attributes
def _resolve_placeholder(name, template=None, local_vars=None,
                         global_vars=None, default=Unspecified):
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
    ph = _resolve_from_search_list(template.search_list, name)
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


def _resolve_placeholder_2(name, template=None, local_vars=None,
                           global_vars=None, default=Unspecified):
  """A slightly different version of resolve_placeholder that relies mostly on
  the accelerated C resolving stuff.
  """
  search_list = [local_vars, template]
  search_list += template.search_list
  search_list += (global_vars, __builtin__)
  return_value = _resolve_from_search_list(search_list, name, default)
  if return_value is not Unspecified:
    return return_value
  else:
    return UndefinedPlaceholder(name,
                                [get_available_placeholders(scope)
                                 for scope in search_list])

resolve_placeholder = _resolve_placeholder


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


def _resolve_from_search_list(search_list, name, default=Unspecified):
  try:
    for scope in search_list:
      try:
        return scope[name]
      except (TypeError, KeyError):
        pass

      try:
        return getattr(scope, name)
      except AttributeError:
        pass
  except TypeError:
    # if this isn't iterable, let's just return UndefinedPlaceholder
    pass
  
  if default != Unspecified:
    return default
  else:
    return UnresolvedPlaceholder


def _resolve_from_search_list_2(search_list, name, default=Unspecified):
  """Models the C function more precisely. However, due to common access
  patterns, it's probably better to prefer dictionaries when resolving from
  a search list. That's just a lot more likely scenario."""
  try:
    for scope in search_list:
      if hasattr(scope, name):
        return getattr(scope, name)
      try:
        return scope[name]
      except (KeyError, TypeError):
        pass
  except TypeError:
    # if this isn't iterable, let's just return UndefinedPlaceholder
    pass
  
  if default != Unspecified:
    return default
  else:
    return UnresolvedPlaceholder
  

def get_available_placeholders(scope):
  if isinstance(scope, dict):
    return scope.keys()
  else:
    return [a for a in dir(scope)
            if not (a.startswith('__') and a.endswith('__'))]


# apply some acceleration if this c module is available
try:
  from spitfire.runtime import _udn
  _c_resolve_from_search_list = _udn._resolve_from_search_list
  _c_resolve_udn = _udn._resolve_udn
except ImportError, e:
  _udn = None


_python_resolve_from_search_list = _resolve_from_search_list
_python_resolve_udn = _resolve_udn
resolve_udn = _resolve_udn

def set_accelerator(enabled=True, enable_test_mode=False):
  """Some key functions are much faster in C.
  They can subtlely change how data is accessed with can cause false-positive
  errors in certain test cases, so we want to be able to toggle it on/off.
  """
  global _resolve_from_search_list
  global _resolve_udn
  global resolve_udn

  if enabled and _udn:
    _resolve_from_search_list = _c_resolve_from_search_list
    _resolve_udn = _c_resolve_udn
  else:
    _resolve_from_search_list = _python_resolve_from_search_list
    if enable_test_mode:
      # use this resolver so that we don't call resolve tester attributes twice
      # automatically - this screws up testing hoisting and other things that
      # are designed to limit calls to resolve_placeholder
      _resolve_udn = resolve_udn_prefer_attr
    else:
      _resolve_udn = _python_resolve_udn

  resolve_udn = _resolve_udn

  if enabled and _udn is None:
    logging.warning('unable to enable acceleration, _udn module not loaded')


# give it our best shot
set_accelerator()
