# a few helpful filter functions

from spitfire.runtime.udn import UndefinedPlaceholder

# decorate a function object so the default filter will not be applied to the
# value of a placeholder. this is handy when building functions that will
# create data that could be double-escaped and you don't wnat to constantly
# inform spitfire to us raw mode.
def skip_filter(function):
  function.skip_filter = True
  return function

def passthrough_filter(template_instance, value):
  return value

@skip_filter
def escape_html(template_instance, value, quote=True):
  """Replace special characters '&', '<' and '>' by SGML entities."""
  value = safe_values(template_instance, value)
  if isinstance(value, basestring):
    value = value.replace("&", "&amp;") # Must be done first!
    value = value.replace("<", "&lt;")
    value = value.replace(">", "&gt;")
    if quote:
      value = value.replace('"', "&quot;")
  return value

def safe_values(template_instance, value):
  if isinstance(value, (str, unicode, int, long, float, UndefinedPlaceholder)):
    return value
  else:
    return ''

# test function for function registry - don't use
@skip_filter
def escape_html_function(value):
  return escape_html(None, value)
