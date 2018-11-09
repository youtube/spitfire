# Quick Installation Notes #

Copy this code into an file called example.spt:
```
<html>
  <head>
    <title>Spitfire example</title>
  </head>
  <body><p>Hello, $name!</p></body>
</html>
```

Download spitfire into some convenient directory, then build and install it:
```
$ git clone https://github.com/youtube/spitfire.git spitfire-read-only
$ cd spitfire-read-only
$ python ./setup.py build
$ python ./setup.py install
```

Run the compiler on your example file.
```
spitfire-compiler example.spt
```
This will produce a file called example.py. Now start up your python interpreter and try the following:
```
import example
data = example.example(search_list=[{'name':"Trurl"}]).main()
print data
```

You should see the template text, but with "name" substituted for "Trurl".
