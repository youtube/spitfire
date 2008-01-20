# a few helpful filter functions

def passthrough_filter(template_instance, value):
  return value

def escape_html(template_instance, value, quote=None):
  """Replace special characters '&', '<' and '>' by SGML entities."""
  value = safe_values(template_instance, value)
  value = value.replace("&", "&amp;") # Must be done first!
  value = value.replace("<", "&lt;")
  value = value.replace(">", "&gt;")
  if quote:
    value = value.replace('"', "&quot;")
  return value


def safe_values(template_instance, value):
  if isinstance(value, (str, unicode, int, long, float)):
    return value
  else:
    return ''
