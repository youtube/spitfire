This is a basic search template that I use a few hundred times a day in my desktop search tool.

```
#from spitfire.runtime.filters import escape_html
#filter escape_html
<html>
  <head>
    <title>search results - "$qstring"</title>
  </head>
  <body>
    <p>
      <form action="/search" method="get">
        <input name="q" type="text" value="$qstring" size="50" />
        <input name="s" type="submit" value="Search" />
      </form>
    </p>
    <p style="font-size:smaller;">
      Showing 1 - $num_results of $total_hits
      <span style="font-size:smaller;color:grey;">(q:${query_time|format_string='%.3f'} t:$total_time)</span>
    </p>
    #for $result in $results
    <p>
      <a href="$result.file_url">$result.title</a>
      <br/>
      <span style="font-size:smaller;">${result.snippet|raw}</span>
      <br/>
      <span style="font-size:smaller; color:green;">
        <a style="color:green;" href="$result.file_path">$result.short_path</a>
        -
        <a title="text size: $result.text_size">$result.size</a>
        -
        $result.time_modified
      </span>
    </p>
    #end for
  </body>
</html>
```