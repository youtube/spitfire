# resolve unified-dotted-notation
# this means search objects and dictionaries in the same way
# using attribute-like syntax from python
# syntactically, 'name' will always be a valid identifier - so you won't get
# name='my attribute' - it must be a legal python identifier

# create a sentinel value for missing attributes
class __MissingAttr(object):
  pass
MissingAttr = __MissingAttr()

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

resolve_udn = resolve_udn_prefer_attr3
