##
## Name:     test_scrubby.py
## Purpose:  Unit tests for scrubby.py
##
## Copyright (C) 2009, Michael J. Fromberger, All Rights Reserved.
##
import scrubby as S
import unittest, functools

# {{ class test_scanner


class test_scanner(unittest.TestCase):
    """Low-level tests for the markup_scanner class.  Only tests the internal
    methods; higher-level methods should be tested by using the results in a
    markup_parser.
    """

    def test_empty_input(self):
        """Test correct scan of empty input."""
        ts = list(S.markup_scanner('').scan())
        self.assertEqual(ts, [('eof', 0, 0, None)])

    def test_strings(self):
        """Test quoted string tokens."""
        for tag, src in (
            ('str', '"double-quoted string"'),
            ('ustr', '"incomplete string'),
            ('str', "'single-quoted string'"),
            ('ustr', "'incomplete string"),
            ('str', '""'),  # empty double-quoted
            ('str', "''"),  # empty single-quoted
            ('ustr', '"\x01'),  # incomplete double-quoted
            ('ustr', "'\x01"),  # incomplete single-quoted
        ):
            s = S.markup_scanner(src)
            self.assertEqual(s.scan_string(0), (tag, 0, len(s.input)))

    def test_unquoted(self):
        """Test unquoted string tokens."""
        s = S.markup_scanner('unquoted string')
        self.assertEqual(s.scan_unquoted(0), ('unq', 0, len('unquoted')))

        s = S.markup_scanner(' empty')
        self.assertEqual(s.scan_unquoted(0, allow_blank=True), ('unq', 0, 0))
        self.assertRaises(S.parse_error,
                          lambda: s.scan_unquoted(0, allow_blank=False))

        s = S.markup_scanner('NAME<')
        self.assertEqual(s.scan_name(0), ('name', 0, len('NAME')))

    def test_space(self):
        """Test whitespace consumption."""
        s = S.markup_scanner('nospace')
        self.assertEqual(s.scan_space(0), ('ws', 0, 0))
        s = S.markup_scanner(' \t\f\r\n$')
        self.assertEqual(s.scan_space(0), ('ws', 0, len(s.input) - 1))

    def test_literal(self):
        """Test consumption of literals."""
        s = S.markup_scanner('$++OK')
        self.assertEqual(s.scan_literal(1, '++'), ('lit', 1, 1 + len('++')))
        self.assertRaises(S.parse_error, lambda: s.scan_literal(0, 'XXX'))

    def test_entity(self):
        """Test consumption of entities."""
        for src in ('&ok', '&123', '&a1bx3c'):
            s = S.markup_scanner(src)
            self.assertEqual(s.scan_entity(1), ('uent', 1, len(s.input)))

            s = S.markup_scanner(src + ';')
            self.assertEqual(s.scan_entity(1), ('ent', 1, len(s.input)))

        s = S.markup_scanner('&$;')
        self.assertEqual(s.scan_entity(1), ('uent', 1, 1))

    def test_comment(self):
        """Test comment tokens."""
        s = S.markup_scanner('<!---->')
        self.assertEqual(s.scan_comment(0), ('com', 0, len(s.input)))

        s = S.markup_scanner('<!-- some random stuff')
        self.assertEqual(s.scan_comment(0), ('ucom', 0, len(s.input)))

        s = S.markup_scanner('!<FAIL')
        self.assertRaises(S.parse_error, lambda: s.scan_comment(0))

    def test_directives(self):
        """Test CDATA and other directives."""
        s = S.markup_scanner('<!normal directive>')
        t = len(s.input)
        self.assertEqual(s.parse_one(0), ('dir', 0, t, {
            'content': (2, t - 1),
            'name': (2, 2 + len('normal'))
        }))
        s = S.markup_scanner('<!broken directive<')
        t = len(s.input)
        self.assertEqual(s.parse_one(0), ('udir', 0, t - 1, {
            'content': (2, t - 1),
            'name': (2, 2 + len('broken'))
        }))

        s = S.markup_scanner('<![CDATA[a[<]]*>+y<]]>')
        t = len(s.input)
        self.assertEqual(s.parse_one(0), ('cdata', 0, t, {
            'content': (len('<![CDATA['), t - len(']]>'))
        }))
        s = S.markup_scanner('<![CDATA[...')
        t = len(s.input)
        self.assertEqual(s.parse_one(0), ('udata', 0, t, {
            'content': (len('<![CDATA['), t)
        }))

    def test_attrib(self):
        """Test tag-attribute tokens."""
        s = S.markup_scanner('novalue/')
        nlen = len('novalue')
        self.assertEqual(s.parse_attrib(0), ('attr', 0, nlen, {
            'name': (0, nlen),
            'value': ('none', nlen, nlen)
        }))
        s = S.markup_scanner('name=bare word')
        nlen = len('name')
        self.assertEqual(s.parse_attrib(0), ('attr', 0, len(s.input) - 5, {
            'name': (0, nlen),
            'value': ('unq', 5, 9)
        }))
        s = S.markup_scanner('name="bare word')
        self.assertEqual(s.parse_attrib(0), ('attr', 0, len(s.input), {
            'name': (0, nlen),
            'value': ('ustr', 5, len(s.input))
        }))
        s = S.markup_scanner(s.input + '"')
        self.assertEqual(s.parse_attrib(0), ('attr', 0, len(s.input), {
            'name': (0, nlen),
            'value': ('str', 5, len(s.input))
        }))


# }}

# {{ class test_parser


class test_parser(unittest.TestCase):
    """Unit tests for markup_parser."""

    def test_directive(self):
        """Test markup directives."""
        s = S.markup_parser('<!DOCTYPE html public>')
        self.assertEqual(len(s), 2)
        self.assertEqual(s[0].type, 'dir')
        self.assertEqual(s[0].name, 'DOCTYPE')
        self.assertEqual(s[0].innersource, 'DOCTYPE html public')

        s = S.markup_parser('<?xml ... ?>')
        self.assertEqual(len(s), 2)
        self.assertEqual(s[0].type, 'dir')
        self.assertEqual(s[0].name, 'xml')
        self.assertEqual(s[0].innersource, 'xml ... ')

        for src in ('<!', '<?'):
            s = S.markup_parser(src + 'incomplete')
            self.assertEqual(len(s), 2)
            self.assertEqual(s[0].type, 'udir')
            self.assertEqual(s[0].name, 'incomplete')
            self.assertEqual(s[0].innersource, 'incomplete')

            s = S.markup_parser(src)
            self.assertEqual(len(s), 2)
            self.assertEqual(s[0].type, 'text')
            self.assertEqual(s[0].source, s.input)

        for src in ('<!>', '<??>'):
            s = S.markup_parser(src)
            self.assertEqual(len(s), 2)
            self.assertEqual(s[0].type, 'text')
            self.assertEqual(s[0].source, s.input)

    def test_tags(self):
        """Test tag formats."""
        s = S.markup_parser('<open1><open2 bare name1=val name2="foo">')
        self.assertEqual(len(s), 3)
        self.assertTagShape(s[0], 'open', 'open1')
        self.assertTagShape(s[1],
                            'open',
                            'open2',
                            bare='',
                            name1='val',
                            name2='foo')

        s = S.markup_parser("<self foo=bar baz='quux crunch' zot/></endtag>")
        self.assertEqual(len(s), 3)
        self.assertTagShape(s[0],
                            'self',
                            'self',
                            foo='bar',
                            baz='quux crunch',
                            zot='')
        self.assertTagShape(s[1], 'close', 'endtag')

    def test_basic_nesting(self):
        """Test basic tag nesting rules."""
        # test indices        0  1  2  3  4  5  6   7   8  9  10
        s = S.markup_parser('<A> w <B> x <C> y <D></B></C> z </A>')
        self.assertChildOf(s[0], None)  # <A>  is at the top level
        self.assertChildOf(s[1], s[0])  # w    is a child of <A>
        self.assertChildOf(s[2], s[0])  # <B>  is a child of <A>
        self.assertChildOf(s[3], s[2])  # x    is a child of <B>
        self.assertChildOf(s[4], s[0])  # <C>  is a child of <A>
        self.assertChildOf(s[5], s[2])  # y    is a child of <B>
        self.assertChildOf(s[6], s[2])  # <D>  is a child of <B>
        self.assertChildOf(s[7], s[0])  # </B> is a child of </A>
        self.assertChildOf(s[8], s[0])  # </C> is a child of <A>
        self.assertChildOf(s[9], s[0])  # z    is a child of <A>
        self.assertChildOf(s[10], None)  # </A> is at the top level

        # Partnership tests
        self.assertPartners(s[0], s[10])
        self.assertPartners(s[2], s[7])
        self.assertPartners(s[4], s[8])

        # Path tests
        # <A> ==> <B> ==> <D>
        self.assertEqual(s[6].path, [s[0], s[2], s[6]])
        # <A> ==> <B> ==> y
        self.assertEqual(s[5].path, [s[0], s[2], s[5]])
        # <A> ==> <C>
        self.assertEqual(s[4].path, [s[0], s[4]])

    def test_custom_nesting(self):
        """Test some simple customized nesting rules."""

        class TP(S.markup_parser):
            CLOSED_BY_CLOSE = {'c': set(('b', ))}
            CLOSED_BY_OPEN = {'c': set(('c', ))}

        #       0  1  2  3  4 5  6 7  8 9   10 11
        s = TP('<A>aaa<B><C>c1<C>c2<C>c3</B>bbb</A>')

        self.assertPartners(s[0], s[11])  # <A> ~ </A>
        self.assertPartners(s[2], s[9])  # <B> ~ </B>
        self.assertPartner(s[3], s[5])  # <C> ~ <C>
        self.assertPartner(s[5], s[7])  # ditto
        self.assertPartner(s[7], s[9])  # ditto

        self.assertChildOf(s[1], s[0])  # A contains aaa
        self.assertChildOf(s[2], s[0])  # A contains B
        self.assertChildOf(s[3], s[2])  # B contains C's
        self.assertChildOf(s[5], s[2])
        self.assertChildOf(s[7], s[2])

        self.assertChildOf(s[4], s[3])  # C's contain their c's
        self.assertChildOf(s[6], s[5])
        self.assertChildOf(s[8], s[7])

        self.assertChildOf(s[10], s[0])  # A contains bbb

    def test_simple_queries(self):
        """Test simple .find() and .first() queries."""
        s = S.markup_parser('<doc><!-- comment -->text<?dir?>'
                            '<atag x=y><tag><self/>more&amp;</tag>')

        # Check that we don't find things we're not supposed to
        self.assertEqual(list(s.find(name='none')), [])
        self.assertRaises(KeyError, lambda: s.first(name='none'))
        self.assertRaises(KeyError,
                          lambda: s.first(name='DOC', case_matters=True))

        # Make sure we find the things we are supposed to
        self.assertEqual(s.first(type='com').source, '<!-- comment -->')
        self.assertEqual(s.last(name='tag').partner.source, '<tag>')
        self.assertEqual(list(t.source for t in s.find(type='text')),
                         ['text', 'more&amp;'])
        self.assertEqual(s.first(value='more&').obj_id, 7)
        self.assertEqual(s.first(type='self').source, '<self/>')
        self.assertEqual(s.first(type='dir').source, '<?dir?>')

        # Check that attribute matching works
        self.assertRaises(KeyError,
                          lambda: s.first(name='atag', attr=('x', False)))
        self.assertRaises(TypeError, lambda: s.first(attr=False))
        self.assertEqual(s.first(name='atag').keys(), ['x'])
        self.assertEqual(s.first(attr=('x', True))['x'].value, 'y')

    def test_query_mapping(self):
        """Test mapping functions over query results."""
        s = S.markup_parser('<a><b/>foobar<c></a></c>')

        self.assertEqual(s.first(type='text', map='source'), 'foobar')
        self.assertEqual(s.first(type='self', map='start'), 3)
        self.assertEqual(s.first(type='close', map=('name', 'obj_id')),
                         ('a', 4))
        self.assertEqual(list(s.find(map=len)),
                         [3, 4, 6, 3, 4, 4, 0])  # includes eof marker
        self.assertEqual(list(s.find(map=lambda t: t.linepos[1])),
                         [0, 3, 7, 13, 16, 20, 24])  #includes eof marker

    def test_query_candidates(self):
        """Test queries that stipulate a particular candidate set."""
        #                    0  1             2   3           4
        s = S.markup_parser('<T>a span of text<U/>another span</T>')

        # If no candidate set is given, search the entire set.
        self.assertEqual(s.first(type='text').obj_id, 1)

        # Search on an object queries the contents of the object.
        self.assertEqual(s[0].first(type='text').obj_id, 1)

        # Search with an explicit range restricts the span.
        self.assertEqual(s.first(type='text', search_after=s[2]).obj_id, 3)

        # Multiple restrictions are allowed.
        self.assertEqual(
            s.first(search_after=s[1], search_before=s[3]).obj_id, 2)
        self.assertEqual(
            s.first(search_after=s[2], search_inside=s[0]).obj_id, 3)
        self.assertEqual(s[0].first(search_after=s[2], type='text').obj_id, 3)
        self.assertEqual(s[0].first(search_before=s[2], type='text').obj_id, 1)

        # Regression: Searching inside a text field doesn't search everything.
        self.assertRaises(KeyError, lambda: s.first(search_inside=s[1]))
        self.assertRaises(KeyError, lambda: s[1].first())

    def test_line_numbers(self):
        """Test line numbering support."""
        # Corner cases: Empty string, single line.
        self.assertEqual(S.markup_parser('').get_linecount(), 1)
        self.assertEqual(S.markup_parser('a').get_linecount(), 1)
        self.assertEqual(S.markup_parser('a\n').get_linecount(), 1)

        s = S.markup_parser('<line num=1>\nline 2\nline 3')
        self.assertEqual(s.get_linecount(), 3)
        self.assertEqual(s.get_line(1), '<line num=1>\n')
        self.assertEqual(s.get_line(2), 'line 2\n')
        self.assertEqual(s.get_line(3), 'line 3')
        self.assertRaises(IndexError, lambda: s.get_line(4))

        t = s.first(type='text')
        self.assertEqual(t.source, '\nline 2\nline 3')
        self.assertEqual(t.linepos, (1, 12))
        self.assertEqual(s.locate(t.start + 1), t)

        self.assertEqual(s.locate(len(s.input)).type, 'eof')

        t = s.locate(7)
        self.assertEqual(t.type, 'open')
        self.assertEqual(t.name, 'num')
        self.assertEqual(t.value, '1')

    def test_white_filter(self):
        """Test whitespace filtering."""
        s = S.markup_parser('  <t0>  <t1/> t2 <t3 num=3> ',
                            skip_white_text=True)
        self.assertEqual(len(s), 5)
        self.assertTagShape(s[0], 'open', 't0')
        self.assertTagShape(s[1], 'self', 't1')
        self.assertObjectShape(s[2], 'text', source=' t2 ')
        self.assertTagShape(s[3], 'open', 't3', num='3')
        self.assertObjectShape(s[4], 'eof')

    def test_positions(self):
        """Test line number, character offset, and column number finding."""
        s = S.markup_parser('<a>\n\t<b/>\t<c>d\n</c>\t</a>')
        s.LINE_NUM_BASE = 1
        s.COLUMN_NUM_BASE = 0
        s.TAB_WIDTH = 8

        # Edge case: First line, first column.
        self.assertEqual(s[0].linepos, (1, 0))
        self.assertEqual(s[0].linecol, (1, 0))
        self.assertEqual(s[2].linepos, (2, 1))
        self.assertEqual(s[2].linecol, (2, 8))

        # Conversion of line/offset and line/column into input offsets.
        self.assertEqual(s.get_offset(1, 0), 0)  # beginning
        self.assertEqual(s.get_offset(2, 9), 13)  # at d
        self.assertEqual(s.get_offset(2, 0), 4)  # start of <b>
        self.assertEqual(s.get_column_offset(1, 0), 0)  # beginning
        self.assertEqual(s.get_column_offset(2, 19), 13)  # at d
        self.assertEqual(s.get_column_offset(2, 8), 5)  # start of <b>

    def test_entities(self):
        """Test entity substitution."""
        s = S.markup_parser('a&lt;b&gt;c&quot;<x>'  # 0 1
                            '--&testName;--<x>'  # 2 3
                            '--&NoneSuch;--<x>'  # 4 5
                            '&#32;&&&#9;')  # 6 <eof>
        self.assertEqual(len(s), 8)

        # Check default entities
        self.assertObjectShape(s[0], 'text', value='a<b>c"')

        # Check custom entities
        s.ENTITY_NAME_MAP['testName'] = '[ok]'
        self.assertObjectShape(s[2], 'text', value='--[ok]--')
        self.assertObjectShape(s[4], 'text', value='--&NoneSuch;--')

        # Check numeric entities
        self.assertObjectShape(s[6], 'text', value=' &&\t')

    def assertChildOf(self, child, parent):
        self.assertEqual(child.parent, parent)

    def assertChildrenOf(self, children, parent):
        for child in children:
            self.assertChildOf(child, parent)

    def assertPartners(self, t1, t2):
        self.assertEqual(t1.partner, t2)
        self.assertEqual(t2.partner, t1)

    def assertPartner(self, t1, t2):
        self.assertEqual(t1.partner, t2)

    def assertObjectShape(self, obj, type, **kvs):
        self.assertEqual(obj.type, type)
        for k, v in kvs.items():
            if not hasattr(obj, k):
                self.fail("expected property {0}, but it is missing".format(k))
            self.assertEqual(getattr(obj, k), v)

    def assertTagShape(self, tag, type, name, **kvs):
        self.assertEqual(tag.type, type)
        self.assertEqual(tag.name, name)
        if hasattr(tag, 'keys'):
            self.assertEqual(sorted(tag.keys()), sorted(kvs))
            for k, v in kvs.items():
                self.assertEqual(tag[k].value, v)
        elif kvs:
            self.fail("expected attributes, but there are none")


# }}

# {{ class test_html


class test_html(test_parser):
    """Unit tests for html_parser."""

    def test_html_nesting(self):
        """Test HTML nesting rules."""
        s = S.html_parser('<html><head> a <body> b </html>')
        self.assertChildOf(s[0], None)
        self.assertChildOf(s[1], s[0])
        self.assertChildOf(s[3], s[0])
        self.assertChildOf(s[5], None)

        self.assertPartners(s[0], s[5])
        self.assertPartner(s[1], s[3])  # <head> closed by <body>
        self.assertPartner(s[3], s[5])  # <body> closed by </html>

        self.assertEqual(s[0].children, [s[1], s[3]])
        self.assertEqual(s[1].children, [s[2]])
        self.assertEqual(s[3].children, [s[4]])

        # Path: <html> ==> <body> ==> b
        self.assertEqual(s[4].path, [s[0], s[3], s[4]])
        # Path: <html> ==> <head> ==> a
        self.assertEqual(s[2].path, [s[0], s[1], s[2]])

        s = S.html_parser('<html>...')
        self.assertPartner(s[0], s[2])  # <html> closed by EOF

        # Table nesting rules.
        # Test table format
        #  x y
        #  a b
        # Indices:          0      1   2  3 4  5 6   7  8 9  10 11
        s = S.html_parser('<table><tr><td>x<td>y<tr><td>a<td>b</table>')
        self.assertChildrenOf((s[1], s[6]), s[0])
        self.assertChildrenOf((s[2], s[4]), s[1])
        self.assertChildrenOf((s[7], s[9]), s[6])
        self.assertChildOf(s[3], s[2])
        self.assertChildOf(s[5], s[4])
        self.assertChildOf(s[8], s[7])
        self.assertChildOf(s[10], s[9])

        # }}


if __name__ == "__main__":
    unittest.main()

# Here there be dragons
