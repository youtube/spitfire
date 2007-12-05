# -*- encoding: utf-8 -*-
# Template language benchmarks
#
# Objective: Generate a 1000x10 HTML table as fast as possible.
#
# Author: Jonas Borgström <jonas@edgewall.com>

import cgi
import sys
import timeit
import StringIO
import cStringIO
try:
    from genshi.builder import tag
    from genshi.template import MarkupTemplate
    from genshi.template import TextTemplate as NewTextTemplate
except ImportError:
    MarkupTemplate = None
    NewTextTemplate = None
    genshi = None

try:
    from elementtree import ElementTree as et
except ImportError:
    et = None

try:
    import cElementTree as cet
except ImportError:
    cet = None

try:
    import neo_cgi, neo_cs, neo_util
except ImportError:
    neo_cgi = None

try:
    import kid
except ImportError:
    kid = None

try:
    from django.conf import settings
    settings.configure()
    from django.template import Context as DjangoContext
    from django.template import Template as DjangoTemplate
except ImportError:
    DjangoContext = DjangoTemplate = None

try:
    from mako.template import Template as MakoTemplate
except ImportError:
    MakoTemplate = None

try:
    import spitfire as SpitfireTemplate
except ImportError:
    SpitfireTemplate = None

try:
    from Cheetah import Template as CheetahTemplate
except ImportError:
    CheetahTemplate = None

table = [dict(a=1,b=2,c=3,d=4,e=5,f=6,g=7,h=8,i=9,j=10)
          for x in range(1000)]

if MakoTemplate:
    genshi_tmpl = MarkupTemplate("""
<table xmlns:py="http://genshi.edgewall.org/">
<tr py:for="row in table">
<td py:for="c in row.values()" py:content="c"/>
</tr>
</table>
""")

    genshi_tmpl2 = MarkupTemplate("""
<table xmlns:py="http://genshi.edgewall.org/">$table</table>
""")

    genshi_text_tmpl = NewTextTemplate("""
<table>
{% for row in table %}<tr>
{% for c in row.values() %}<td>$c</td>{% end %}
</tr>{% end %}
</table>
""")

if DjangoTemplate:
    django_tmpl = DjangoTemplate("""
    <table>
    {% for row in table %}
    <tr>{% for col in row.values %}{{ col|escape }}{% endfor %}</tr>
    {% endfor %}
    </table>
    """)

    def test_django():
        """Djange template"""
        context = DjangoContext({'table': table})
        django_tmpl.render(context)

if MakoTemplate:
    mako_tmpl = MakoTemplate("""
<table>
  % for row in table:
    <tr>
      % for col in row.values():
        <td>${ col | h  }</td>
      % endfor
    </tr>
  % endfor
</table>
""")
    def test_mako():
        """Mako Template"""
        data = mako_tmpl.render(table=table)
        #print "mako", len(data)

if SpitfireTemplate:
    import spitfire.compiler.analyzer
    import spitfire.compiler.util
    spitfire_src = """<table xmlns:py="http://spitfire/">
#for $row in $table
<tr>
#for $column in $row.values()
<td>$column</td>
#end for
</tr>
#end for
</table>
"""

    spitfire_tmpl = spitfire.compiler.util.load_template(
        spitfire_src, 'spitfire_tmpl')

    spitfire_tmpl_o1 = spitfire.compiler.util.load_template(
        spitfire_src, 'spitfire_tmpl_o1', spitfire.compiler.analyzer.o1_options)

    spitfire_tmpl_o2 = spitfire.compiler.util.load_template(
        spitfire_src, 'spitfire_tmpl_o2', spitfire.compiler.analyzer.o2_options)

    spitfire_tmpl_o3 = spitfire.compiler.util.load_template(
        spitfire_src, 'spitfire_tmpl_o3', spitfire.compiler.analyzer.o3_options)
    # run once to get psyco warmed up
    spitfire_tmpl_o3(search_list=[{'table':table}]).main()


    def test_spitfire():
        """Spitfire template"""
        data = spitfire_tmpl(search_list=[{'table':table}]).main()
        #print "spitfire", len(data)

    def test_spitfire_o1():
        """Spitfire template -O1"""
        data = spitfire_tmpl_o1(search_list=[{'table':table}]).main()
        #print "spitfire -O1", len(data)

    def test_spitfire_o2():
        """Spitfire template -O2"""
        data = spitfire_tmpl_o2(search_list=[{'table':table}]).main()
        #print "spitfire -O2", len(data)

    def test_spitfire_o3():
        """Spitfire template -O3"""
        data = spitfire_tmpl_o3(search_list=[{'table':table}]).main()
        #print "spitfire -O3", len(data)

if CheetahTemplate:
    cheetah_src = """<table>
#for $row in $table
<tr>
#for $column in $row.values()
<td>$column</td>
#end for
</tr>
#end for
</table>"""
    pre = set([k for k, v in sys.modules.iteritems() if v])
    cheetah_template = CheetahTemplate.Template(cheetah_src, searchList=[{'table':table}])
    # force compile
    post = set([k for k, v in sys.modules.iteritems() if v])
    #print post - pre
    
    #print type(cheetah_template)
    cheetah_template.respond()
    cheetah_template = type(cheetah_template)

    def test_cheetah():
        """Cheetah template"""
        data = cheetah_template(searchList=[{'table':table}]).respond()
        #print "cheetah", len(data)

if genshi:
    def test_genshi():
        """Genshi template"""
        stream = genshi_tmpl.generate(table=table)
        data = stream.render('html', strip_whitespace=False)
        #print "genshi", len(data)

    def test_genshi_text():
        """Genshi text template"""
        stream = genshi_text_tmpl.generate(table=table)
        print "test_genshi_text", stream
        data = stream.render('text')
        print "test_genshi_text", 'data', stream

    def test_genshi_builder():
        """Genshi template + tag builder"""
        stream = tag.TABLE([
            tag.tr([tag.td(c) for c in row.values()])
            for row in table
        ]).generate()
        stream = genshi_tmpl2.generate(table=stream)
        stream.render('html', strip_whitespace=False)

    def test_builder():
        """Genshi tag builder"""
        stream = tag.TABLE([
            tag.tr([
                tag.td(c) for c in row.values()
            ])
            for row in table
        ]).generate()
        stream.render('html', strip_whitespace=False)

if kid:
    kid_tmpl = kid.Template("""
    <table xmlns:py="http://purl.org/kid/ns#">
    <tr py:for="row in table">
    <td py:for="c in row.values()" py:content="c"/>
    </tr>
    </table>
    """)

    kid_tmpl2 = kid.Template("""
    <html xmlns:py="http://purl.org/kid/ns#">$table</html>
    """)

    def test_kid():
        """Kid template"""
        kid_tmpl.table = table
        kid_tmpl.serialize(output='html')

    if cet:
        def test_kid_et():
            """Kid template + cElementTree"""
            _table = cet.Element('table')
            for row in table:
                td = cet.SubElement(_table, 'tr')
                for c in row.values():
                    cet.SubElement(td, 'td').text=str(c)
            kid_tmpl2.table = _table
            kid_tmpl2.serialize(output='html')

if et:
    def test_et():
        """ElementTree"""
        _table = et.Element('table')
        for row in table:
            tr = et.SubElement(_table, 'tr')
            for c in row.values():
                et.SubElement(tr, 'td').text=str(c)
        et.tostring(_table)

if cet:
    def test_cet(): 
        """cElementTree"""
        _table = cet.Element('table')
        for row in table:
            tr = cet.SubElement(_table, 'tr')
            for c in row.values():
                cet.SubElement(tr, 'td').text=str(c)
        cet.tostring(_table)

if neo_cgi:
    def test_clearsilver():
        """ClearSilver"""
        hdf = neo_util.HDF()
        for i, row in enumerate(table):
            for j, c in enumerate(row.values()):
                hdf.setValue("rows.%d.cell.%d" % (i, j), cgi.escape(str(c)))

        cs = neo_cs.CS(hdf)
        cs.parseStr("""
<table><?cs
  each:row=rows
?><tr><?cs each:c=row.cell
  ?><td><?cs var:c ?></td><?cs /each
?></tr><?cs /each?>
</table>""")
        cs.render()

def test_python_cstringio():
    """cStringIO"""
    buffer = cStringIO.StringIO()
    write = buffer.write
    write('<table>\n')
    for row in table:
        write('<tr>\n')
        for col in row.itervalues():
            write('<td>\n')
            write('%s' % col)
            write('\n</td>\n')
        write('</tr>\n')
    write('</table>')
    return buffer.getvalue()

def test_python_stringio():
    """StringIO"""
    buffer = StringIO.StringIO()
    write = buffer.write
    
    write('<table>\n')
    for row in table:
        write('<tr>\n')
        for col in row.itervalues():
            write('<td>\n')
            write('%s' % col)
            write('\n</td>\n')
        write('</tr>\n')
    write('</table>')
    return buffer.getvalue()
    
def test_python_array():
    """list concat"""
    buffer = []
    write = buffer.append
    
    write('<table>\n')
    for row in table:
        write('<tr>\n')
        for col in row.itervalues():
            write('<td>\n')
            write('%s' % col)
            write('\n</td>\n')
        write('</tr>\n')
    write('</table>')
    return ''.join(buffer)


def run(which=None, number=10):
    tests = ['test_builder', 'test_genshi',
             'test_genshi_text',
             'test_genshi_builder', 'test_mako', 'test_kid', 'test_kid_et',
             'test_et', 'test_cet', 'test_clearsilver', 'test_django',
             'test_cheetah',
             'test_spitfire', 'test_spitfire_o1',
             'test_spitfire_o2', 'test_spitfire_o3',
             'test_python_stringio', 'test_python_cstringio', 'test_python_array'
             ]

    if which:
        tests = filter(lambda n: n[5:] in which, tests)

    for test in [t for t in tests if hasattr(sys.modules[__name__], t)]:
        t = timeit.Timer(setup='from __main__ import %s;' % test,
                         stmt='%s()' % test)
        time = t.timeit(number=number) / number

        if time < 0.00001:
            result = '   (not installed?)'
        else:
            result = '%16.2f ms' % (1000 * time)
        print '%-35s %s' % (getattr(sys.modules[__name__], test).__doc__, result)


if __name__ == '__main__':
    which = [arg for arg in sys.argv[1:] if arg[0] != '-']

    if '-p' in sys.argv:
        import hotshot, hotshot.stats
        prof = hotshot.Profile("template.prof")
        benchtime = prof.runcall(run, which, number=1)
        stats = hotshot.stats.load("template.prof")
        stats.strip_dirs()
        stats.sort_stats('time', 'calls')
        stats.print_stats()
    else:
        run(which, 1)
