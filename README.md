![http://spitfire.googlecode.com/svn/wiki/spitfire.png](http://spitfire.googlecode.com/svn/wiki/spitfire.png)

# Introduction #

Spitfire is a template language heavily inspired by Cheetah. It started out as an experiment to see if techniques from the compiler world were applicable to the mundane details of templates.

At this point, Spitfire works - at least in theory. There are basic tests cases that assure templates parse, compile, generate and execute correctly. Most language features are covered with a high-level test, though it is possible that there are some bugs or shortcomings in the syntax.


# Details #

The syntax itself is extremely similar to Cheetah, however there are some directives and language features that have been omitted (usually on purpose).  Trivial Cheetah templates will probably compile in Spitfire, so that's probably a good place to start.

The change log and `parser.g` file are currently the primary source of information on this, which is not the best. I've started documenting the differences in SpitfireVsCheetah.

There's also work being done on an attribute (i.e. XML namespace) variant of the syntax, similar to the TAL and Kid syntaxes, for those of you who like templates that are valid XML/XHTML. We'll add more info on this when it's ready for testing.

There are also some vague notes on the internal CompilerDesign that are probably not useful to the majority of people.

# Examples #

Sometimes a good example is the best way to jump in.
  * SpitfireSearchResultsExample


# Current Release #

[spitfire-0.6.17](http://spitfire.googlecode.com/svn/tags/spitfire-0.6.17)
  * fixes a couple of bugs in optimized output (-O2 or above)

Trunk is semi-stable as there are reasonable regression tests. Go ahead, be brave.

  * [spitfire trunk](http://spitfire.googlecode.com/svn/trunk)



# Release Notes #

I note most of the progress in the [change log](http://spitfire.googlecode.com/svn/trunk/CHANGES). The biggest addition is the alternate front end to support an attribute language (think TAL or Kid).

# Performance #

Spitfire has a basic optimizer that can make certain operations much faster. I found a basic 10x1000 table generation benchmark written by the Genshi team. I modified it to add Cheetah (my baseline performance target) and Spitfire. This is by no means exhaustive proof that Spitfire is always fast, just that in a simple case of burning through a loop of generating text, it's not too shabby.

PN: Note, to run the bigtable test, you'll need psyco http://psyco.sourceforge.net/

```
hannosch:spitfire hannosch$ python tests/perf/bigtable.py
Genshi tag builder                            671.49 ms
Genshi template                               493.39 ms
Genshi template + tag builder                 714.04 ms
Mako Template                                  74.78 ms
ElementTree                                   299.03 ms
cElementTree                                  179.47 ms
Cheetah template                               58.67 ms
Spitfire template                              65.32 ms
Spitfire template -O1                          40.19 ms
Spitfire template -O2                          15.99 ms
Spitfire template -O3                          16.02 ms
Spitfire template -O4                          11.09 ms
StringIO                                       80.85 ms
cStringIO                                      16.52 ms
list concat                                    12.93 ms

hannosch:spitfire hannosch$ python
Python 2.4.5 (#1, Jul 20 2008, 12:34:19) 
[GCC 4.0.1 (Apple Inc. build 5465)] on darwin
>>>
```

Two more examples from the Zope / TAL world:
```
hannosch:z3c.pt hannosch$ bin/py benchmark/benchmark/bigtable.py
z3c.pt template                                25.43 ms
zope.pagetemplate template                    564.55 ms
```

For comparison, here are two samples from PHP.
```
hannosch:spitfire/tests/perf> php4 bigtable.php 
Smarty template:    21.04 ms
PHP:                12.01 ms

hannosch:spitfire/tests/perf> php5 bigtable.php 
Smarty template:    13.16 ms
PHP:                 6.24 ms
```