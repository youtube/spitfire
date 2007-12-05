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
  def __init__(self, index=0):
    self.index = index

  @property
  def number(self):
    return self.index + 1

  @property
  def even(self):
    return not (self.index % 2)

  @property
  def odd(self):
    return (self.index % 2)
