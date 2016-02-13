# Copyright 2015 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

import timeit

from spitfire.runtime import template
from spitfire.runtime import baked


def skip():
    pass


skip.skip_filter = True


def no_skip():
    pass


sp_creation = ['foo', 'adafadfhasdkfh',
               'dsafjadhf dafhaskfh kadsfadfadfasfjakfh',
               'sdfsdfaa  adksj k jasdfljkasdf jka dsf']
mark_as_s = ['foo', object(), 12344345234274.3333,
             'asdfasdf asdjfh asjfd asdfasdf', ['123']]


def time_fn(label, fn, arg):
    if hasattr(arg, '__len__') and len(arg) == 2:
        v, f = arg
        print 'Timing %s - %s(%s, %s)' % (label, fn.__name__, v, f.__name__)
        t = timeit.Timer(lambda: fn(v, f))
    else:
        print 'Timing %s - %s(%s)' % (label, fn.__name__, arg)
        t = timeit.Timer(lambda: fn(arg))
    try:
        r = t.repeat(10, 100000)
    except:  # pylint:disable=bare-except
        t.print_exc()
        return

    best = min(r)
    scale = 1e3 / len(r)
    msec = best * scale
    all = ', '.join('%.1f' % (v * scale) for v in r)
    print 'best run: %.1f msec per loop [%s]' % (msec, all)


def main():
    c_tmpl = template.get_spitfire_template_class(prefer_c_extension=True)()
    py_tmpl = template.get_spitfire_template_class(prefer_c_extension=False)()

    print '*** filter_function with SanitizedPlaceholder'
    for v in sp_creation:
        sp = baked.SanitizedPlaceholder(v)
        time_fn('Py', py_tmpl.filter_function, sp)
        time_fn('C', c_tmpl.filter_function, sp)
        print ''

    print '***filter_function with string'
    for v in sp_creation:
        time_fn('Py', py_tmpl.filter_function, v)
        time_fn('C', c_tmpl.filter_function, v)
        print ''

    print '***filter_function with skip_filter'
    for v in sp_creation:
        time_fn('Py', py_tmpl.filter_function, (v, skip))
        time_fn('C', c_tmpl.filter_function, (v, skip))
        print ''

    print '***filter_function with no skip_filter'
    for v in sp_creation:
        time_fn('Py', py_tmpl.filter_function, (v, no_skip))
        time_fn('C', c_tmpl.filter_function, (v, no_skip))
        print ''


if __name__ == '__main__':
    main()
