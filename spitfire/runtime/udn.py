# Copyright 2007 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

# resolve unified-dotted-notation and placeholders
# this means search objects and dictionaries in the same way
# using attribute-like syntax from python
# syntactically, 'name' will always be a valid identifier - so you won't get
# name='my attribute' - it must be a legal python identifier

import __builtin__
import inspect
import logging
import weakref

from spitfire import runtime
# Import the accelerated C module if available.
try:
    from spitfire.runtime import _udn
except ImportError:
    _udn = None

# Avoid extra lookups on critical paths by aliasing imports directly.
UndefinedAttribute = runtime.UndefinedAttribute
UndefinedPlaceholder = runtime.UndefinedPlaceholder
UnresolvedPlaceholder = runtime.UnresolvedPlaceholder


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

    def __cmp__(self, unused_other):
        raise runtime.PlaceholderError(self.name,
                                       'function placeholder was not called')

    def __nonzero__(self):
        raise runtime.PlaceholderError(self.name,
                                       'function placeholder was not called')


# TODO - optimize performance
def _resolve_udn_prefer_attr(_object, name, raise_exception=False):
    try:
        return getattr(_object, name)
    except AttributeError:
        try:
            return _object[name]
        except (KeyError, TypeError):
            if raise_exception:
                raise runtime.UDNResolveError(name, dir(_object))
            else:
                return UndefinedAttribute(name, dir(_object))


def _resolve_udn_prefer_dict(_object, name, raise_exception=False):
    try:
        return _object[name]
    except (KeyError, TypeError):
        try:
            return getattr(_object, name)
        except AttributeError:
            if raise_exception:
                raise runtime.UDNResolveError(name, dir(_object))
            else:
                return UndefinedAttribute(name, dir(_object))


# this is always faster than catching an exception when that exception isn't
# truly exceptional,  but semi-expected
# using a sentinel should be quicker than calling hasattr then getattr
# this is true when the expected hit rate on an attribute is relatively
# reasonable - say 50% chance
def _resolve_udn_prefer_attr2(_object, name, raise_exception=False):
    val = getattr(_object, name, MissingAttr)
    if val is not MissingAttr:
        return val
    try:
        return _object[name]
    except (KeyError, TypeError):
        if raise_exception:
            raise runtime.UDNResolveError(name, dir(_object))
        else:
            return UndefinedAttribute(name, dir(_object))


# this version is slightly faster when there are a lot of misses on attributes
def _resolve_udn_prefer_attr3(_object, name, raise_exception=False):
    if hasattr(_object, name):
        return getattr(_object, name)
    try:
        return _object[name]
    except (KeyError, TypeError):
        if raise_exception:
            raise runtime.UDNResolveError(name, dir(_object))
        else:
            return UndefinedAttribute(name, dir(_object))


_resolve_udn = _resolve_udn_prefer_attr3


def _resolve_placeholder(name, template, global_vars):
    placeholder_cache = template.placeholder_cache
    if placeholder_cache and name in placeholder_cache:
        ph = placeholder_cache[name]
        if isinstance(ph, weakref.ReferenceType):
            v = ph()
            if v is not None:
                return v
        else:
            return ph

    # Note: getattr with 3 args is somewhat slower if the attribute
    # is found, but much faster if the attribute is not found.
    udn_ph = UndefinedPlaceholder
    result = getattr(template, name, udn_ph)
    if result is not udn_ph:
        if placeholder_cache is not None:
            # Use a weakref for methods to prevent memory cycles.
            placeholder_cache[name] = weakref.ref(result) if inspect.ismethod(
                result) else result
        return result

    search_list = template.search_list
    if search_list:
        ph = resolve_from_search_list(search_list, name)
        if ph is not UnresolvedPlaceholder:
            if placeholder_cache is not None:
                # Use a weakref for methods to prevent memory cycles.
                placeholder_cache[name] = weakref.ref(ph) if inspect.ismethod(
                    ph) else ph
            return ph

    # TODO: Cache negative results in placedholder_cache?
    # This probably isn't worthwhile as it likely won't happen often enough
    # to make the extra code/cpu/memory worthwhile.

    if global_vars is not None:
        try:
            return global_vars[name]
        except KeyError:
            pass
        except TypeError:
            raise runtime.PlaceholderError(
                'unexpected type for global_vars: %s' % type(global_vars))

    # fixme: finally try to resolve builtins - this should be configurable
    # if you compile optimized modes, this isn't necessary
    try:
        return getattr(__builtin__, name)
    except AttributeError:
        return UndefinedPlaceholder(name, search_list)


# FIXME: i'm sure this is a little pokey - might be able to speed this up
# somehow. not sure if it's better to look before leaping or raise.
# might also want to let users tune whether to prefer keys or attributes
def _resolve_placeholder_with_locals(name, template, local_vars, global_vars):
    if local_vars is not None:
        try:
            return local_vars[name]
        except KeyError:
            pass
        except TypeError:
            raise runtime.PlaceholderError(
                'unexpected type for local_vars: %s' % type(local_vars))

    return _resolve_placeholder(name, template, global_vars)


def _debug_resolve_placeholder(name, *pargs, **kargs):
    placeholder = _resolve_placeholder(name, *pargs, **kargs)
    if inspect.isroutine(placeholder):
        return CallOnlyPlaceholder(name, placeholder)
    else:
        return placeholder


def _debug_resolve_udn(_object, name, *pargs, **kargs):
    placeholder = _resolve_udn_prefer_attr3(_object, name, *pargs, **kargs)
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

# Define Python/C alternates.
_python_resolve_from_search_list = _resolve_from_search_list
_python_resolve_udn = _resolve_udn
if _udn:
    _c_resolve_from_search_list = _udn._resolve_from_search_list
    _c_resolve_udn = _udn._resolve_udn

# Set default functions.
resolve_from_search_list = _python_resolve_from_search_list
resolve_udn = _python_resolve_udn
resolve_placeholder = _resolve_placeholder
resolve_placeholder_with_locals = _resolve_placeholder_with_locals


def set_accelerator(enabled=True, enable_test_mode=False):
    """Some key functions are much faster in C.
    They can subtlely change how data is accessed which can cause false-positive
    errors in certain test cases, so we want to be able to toggle it on/off.
    """
    global resolve_from_search_list
    global resolve_udn

    if enabled and _udn:
        resolve_from_search_list = _c_resolve_from_search_list
        resolve_udn = _c_resolve_udn
    elif enable_test_mode:
        resolve_from_search_list = _python_resolve_from_search_list
        # use this resolver so that we don't call resolve tester attributes twice
        # automatically - this screws up testing hoisting and other things that
        # are designed to limit calls to resolve_placeholder
        resolve_udn = _resolve_udn_prefer_attr
    else:
        resolve_from_search_list = _python_resolve_from_search_list
        resolve_udn = _python_resolve_udn

    if enabled and _udn is None:
        logging.warning('unable to enable acceleration, _udn module not loaded')

# give it our best shot
set_accelerator()
