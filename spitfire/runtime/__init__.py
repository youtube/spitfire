# Copyright 2007 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.


class __UnresolvedPlaceholder(object):
    pass


UnresolvedPlaceholder = __UnresolvedPlaceholder()


class PlaceholderError(KeyError):
    pass


class UDNResolveError(Exception):
    pass


# the idea is to have something that is always like None, but explodes when
# you try to use it as a string. this means that you can resolve placeholders
# and evaluate them in complex conditional expressions, allowing them to be
# hoisted, and still protect conditional access to the values
# it could also be that you might try to call the result - in that case, blow
# and exception as well.
class UndefinedPlaceholder(object):

    def __init__(self, name, search_list):
        # Uses mangled names for internal state in case these attributes
        # happen to match the object it's replacing.  eg, if the user_object
        # was an UndefinedPlaceholder in this statement:  $user_object.name
        self.__name = name
        self.__search_list = search_list

    def __nonzero__(self):
        return False

    def __str__(self):
        raise PlaceholderError(self.__name, self.get_placeholder_names())

    def __call__(self, *pargs, **kargs):
        raise PlaceholderError(self.__name, self.get_placeholder_names())

    def get_placeholder_names(self):
        return [_get_available_placeholders(scope)
                for scope in self.__search_list]


class UndefinedAttribute(UndefinedPlaceholder):
    pass


def _get_available_placeholders(scope):
    if isinstance(scope, dict):
        return scope.keys()
    else:
        return [a
                for a in dir(scope)
                if not (a.startswith('__') and a.endswith('__'))]


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
