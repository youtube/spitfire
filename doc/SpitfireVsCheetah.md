# Introduction #

Spitfire is syntactically similar to Cheetah. In fact, most basic Cheetah templates should compile with Spitfire with very minor (potentially zero) modifications.

There are a few notable places where things diverge and some of this is up for debate. Most of the differences stem from the basic philosophy that Spitfire is only for rendering text and logic should be minimal.

# Notable Differences #

### Passing keyword arguments is different. ###

We do not allow whitespace around the '=' and the keyword name itself is not a placeholder - so no '$' is allowed.

You need to do:
```
$function(keyword='value')
```

Instead of:
```
$function($keyword = 'value')
```

You might see this error if you have extra whitespace:
```
Trying to find CLOSE_PAREN on line 15:
>  $function(keyword = 'value')
>                   ^
```
You might see this error if you have an extra dollar sign. Note that the error message is correct, but the error
caret is slightly off.
```
keyword arg cant be complex expression: PlaceholderNode keyword on line 15:
>  $function($keyword='value')
>                     ^
```

### Spitfire does not do autocalling. ###

If you want to call a function, you must explicitly do so. This is the opposite of Cheetah's default behavior.  The default filter in Spitfire will replace references to function objects with empty strings.

### Spitfire does not allow slicing of arrays. ###

```
#for $user in $recent_users[:10]
...
#end for
```

This is legal in Cheetah, but not Spitfire. The rationale is that the servlet or controller code should be doing this. Since the template and servlet are disjoint, slicing in the template is a good way of ensuring that eventually your backend is doing more work than it needs to. Over-fetching data burns resources and should be discouraged.

### Multiple #extends directives are fine. ###

In Cheetah, multiple inheritance is not allowed by default.  In Spitfire, it's sort of encouraged. The terminology is not ideal - really you are importing the behavior of another template, which happens to be implemented behind the scenes as multiple inheritance.

```
#extends base_html ## sets up a standard html page
#extends layout.three_column ## sets up some more html and gives you three defined areas

#def column1()
Hello column one!
#end def
```

### Missing Directives ###

There are a number of directives that have been omitted, at least for the time being. The main motivation is that in more than three years of working with Cheetah, I've never used most of these myself. When I see them used, it's usually some hack, not something well thought out - with a few notable exceptions.
  * #assert
  * #breakpoint
  * #cache
  * #compiler-setttings
  * #include
  * #del
  * #echo
  * #encoding
    * everything is internally handled as unicode objects and templates are always considered to be in UTF8
  * #errorCatcher
  * #pass
  * #raise
  * #repeat
  * #set global
  * #silent
  * #stop
  * #try ... #except ... #finally ... #end try
  * #unless
  * #while

### Placeholders and filters should be easier to use in the end. ###

These are handled a little differently internally to avoid issues like double-escaping.  The default filter in Spitfire basically allows int/long, float, str and unicode objects through.  Anything else is replaced with empty string when the output is written.

  * `$hasVar` and `$getVar` are replaced by `$has_var` and `$get_var` - this is slightly an annoyance and there's not a fantastic reason for it, other than internal naming consistency
  * trivial placeholders should be treated identically
  * extended placeholders (those wrapped in braces) have other properties
    * `${placeholder_expression}`
    * `${placeholder_expression|filter=html_escape}` - override the filter on this instance
    * `${placeholder_expression|raw}` - don't filter at all
    * `${placeholder_expression|format_string='%3.3f'}` - use a format string other than `'%s'`


### Filters are implemented differently. ###

The API is very simple, so it's probably just easiest to look at the code.