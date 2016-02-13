# Copyright 2007 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.


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

    def __init__(self, index=0, item=None, length=None):
        self.index = index
        self.item = item
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


class RepeatIterator(object):

    def __init__(self, iterable):
        self.src_iterable = iterable
        self.src_iterator = enumerate(iterable)
        try:
            self.length = len(iterable)
        except TypeError:
            # if the iterable is a generator, then we have no length
            self.length = None

    def __iter__(self):
        return self

    def next(self):
        index, item = self.src_iterator.next()
        return Repeater(index, item, self.length)
