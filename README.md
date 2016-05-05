# ![Spitfire][]

[![Version][]](https://badge.fury.io/py/spitfire)
[![Status][]](https://travis-ci.org/youtube/spitfire)


## Introduction

Spitfire is a high-performance Python template language inspired
by [Cheetah][].  It originally started out as an experiment to
see if techniques used in compilers were applicable to
templates.  Spitfire has been the primary template language for
[youtube.com][] since 2008 and is used to generate
[billions of views a day][].


## Example

```html
<html>
<head><title>$title</title></head>
<body>
  <ul>
    #for $user in $users
      <li><a href="$user.url">$user.name</a></li>
    #end for
  </ul>
</body>
</html>
```


## Getting Started

Spitfire's syntax is extremely similar to Cheetah, however some
directives and language features have been omitted.  If you're
already using Cheetah, simple templates will likely compile in
Spitfire, and there are a couple compatibility modes to ease
transition.


## Performance

Spitfire has a basic optimizer that can make certain operations
much faster.  Using a basic 10x1000 table generation benchmark,
Spitfire can be faster than other template systems and compares
very favorably to hand-coded Python (the upper limit of
performance achievable by compiling to Python bytecode).
This is by no means exhaustive proof that Spitfire is always
fast, just that it can provide very high performance.

```
# Python 2.7.6 [GCC 4.8.2] on linux, 6-core Intel Xeon E5-1650 V3 @ 3.50GHz
$ python tests/benchmarks/render_benchmark.py  --compare --number 1000
Running benchmarks 1000 times each...

Cheetah template                               18.76 ms
Django template                               263.94 ms
Django template autoescaped                   262.89 ms
Jinja2 template                                 8.52 ms
Jinja2 template autoescaped                    18.22 ms
Mako template                                   3.25 ms
Mako template autoescaped                      11.45 ms
Python string template                         29.78 ms
Python StringIO buffer                         20.92 ms
Python cStringIO buffer                         5.93 ms
Python list concatenation                       2.30 ms
Spitfire template -O3                           6.60 ms
Spitfire template baked -O3                     8.15 ms
Spitfire template unfiltered -O3                2.17 ms
```


[Cheetah]: http://www.cheetahtemplate.org/
[youtube.com]: https://www.youtube.com/
[billions of views a day]: https://www.youtube.com/yt/press/statistics.html

[Spitfire]: https://raw.githubusercontent.com/youtube/spitfire/master/doc/spitfire.png
[Version]: https://badge.fury.io/py/spitfire.svg
[Status]: https://secure.travis-ci.org/youtube/spitfire.svg?branch=master
