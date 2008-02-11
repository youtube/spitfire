# resolve unified-dotted-notation and placeholders
# this means search objects and dictionaries in the same way
# using attribute-like syntax from python
# syntactically, 'name' will always be a valid identifier - so you won't get
# name='my attribute' - it must be a legal python identifier

import __builtin__


# create a sentinel value for missing attributes
class __MissingAttr(object):
  pass
MissingAttr = __MissingAttr()

# sentinel class, in case you want to have a default that is None
class __Unspecified(object):
  pass
Unspecified = __Unspecified()

class __UnresolvedPlaceholder(object):
  pass
UnresolvedPlaceholder = __UnresolvedPlaceholder()

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
def resolve_placeholder(name, template=None, local_vars=None, global_vars=None,
                        default=Unspecified):
  if local_vars is not None:
    try:
      return local_vars[name]
    except TypeError:
      raise PlaceholderError('unexpected type for local_vars: %s' %
                             type(local_vars))
    except KeyError:
      pass

  try:
    return getattr(template, name)
  except AttributeError:
    pass

  if template.search_list is not None:
    for scope in template.search_list:
      try:
        return scope[name]
      except (TypeError, KeyError):
        pass

      try:
        return getattr(scope, name)
      except AttributeError:
        pass

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
    raise PlaceholderError(name,
                           [get_available_placeholders(scope)
                            for scope in template.search_list])

def get_available_placeholders(scope):
  if isinstance(scope, dict):
    return scope.keys()
  else:
    return dir(scope)


resolve_udn = resolve_udn_prefer_attr3
