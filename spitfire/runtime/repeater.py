class RepeatTracker(object):
  def __init__(self):
    self.repeater_map = {}

  def __setitem__(self, key, value):
    try:
      self.repeater_map[key].index = value
    except KeyError, e:
      self.repeater_map[key] = Repeater(value)

  def __getitem__(self, key):
    return self.repeater_map[key]

class Repeater(object):
  def __init__(self, index=0, length=None):
    self.index = index
    self.length = length

  @property
  def number(self):
    return self.index + 1

  @property
  def even(self):
    return not (self.index % 2)

  @property
  def odd(self):
    return (self.index % 2)

  @property
  def first(self):
    return (self.index == 0)

  @property
  def last(self):
    return (self.index == (self.length - 1))

def reiterate(iterable):
  try:
    length = len(iterable)
  except TypeError:
    # if the iterable is a generator, then we have no length
    length = None
  for index, item in enumerate(iterable):
    yield (Repeater(index, length), item)
    
    
    
    
