# resolve unified-dotted-notation
# this means search objects and dictionaries in the same way
# using attribute-like syntax from python
# syntactically, 'name' will always be a valid identifier - so you won't get
# name='my attribute' - it must be a legal python identifier

class UDNResolveError(Exception):
  pass

# TODO - optimize performance
def resolve_udn(_object, name):
  try:
    return getattr(_object, name)
  except AttributeError:
    try:
      return _object[name]
    except (KeyError, TypeError):
      raise UDNResolveError(name, dir(_object))
