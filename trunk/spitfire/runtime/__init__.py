class __UnresolvedPlaceholder(object):
  pass
UnresolvedPlaceholder = __UnresolvedPlaceholder()

class __UnresolvedEntity(object):
  pass
UnresolvedEntity = __UnresolvedEntity()

class PlaceholderError(KeyError):
  pass

class UDNResolveError(Exception):
  pass


def import_module_symbol(name):
  name_parts = name.split('.')
  module_name = '.'.join(name_parts[:-1])
  symbol_name = name_parts[-1]
  module = __import__(module_name, globals(), locals(), [symbol_name])
  try:
    symbol = getattr(module, symbol_name)
  except AttributeError, e:
    raise ImportError("can't import %s" % name)
  return symbol


# map template function names to python function names
# inject them into a module so they run as globals
def register_functions(module, template_function_map):
  for t_name, f_name in template_function_map.iteritems():
    f_func = import_module_symbol(f_name)
    setattr(module, t_name, f_func)
    
# decorate a function object so the value will be retrieved once and then
# cached in the template forever.
def cache_forever(function):
  function.cache_forever = True
  return function

# decorate a function object so its result is not cached in module globals
def never_cache(function):
	function.never_cache = True
	return function

