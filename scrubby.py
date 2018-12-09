##
## Name:     scrubby.py
## Purpose:  A tag-soup parser for HTML and other similar markup languages.
##
## Copyright (C) 2009, Michael J. Fromberger, All Rights Reserved.
##
## Basic usage instructions:
##
## import scrubby
##
## p = scrubby.html_parser('<html><body class="foo">Blah blah</body></html>')
##
## len(p)  ==> 6
## p.input ==> '<html><body class="foo">Blah blah</body></html>'
##
## p[0]    ==> #<markup_tag type='open' name='html' 0..6>
##   p[0].children ==> [#<markup_tag type='open' name='body' 6..24>,
##                      #<markup_tag type='close' name='body' 33..40>]
##   p[0].contents ==> [#<markup_tag type='open' name='body' 6..24>,
##                      #<markup_text type='text' | 24..33>,
##                      #<markup_tag type='close' name='body' 33..40>]
##   p[0].csource  ==> '<body class="foo">Blah blah</body>'
##
## p[1]    ==> #<markup_tag type='open' name='body' 6..24>
##   p[1].source   ==> '<body class="foo">'
##   p[1].keys()   ==> ['class']
##   p[1]['class'] ==> #<markup_attribute tag=1 name='class' 12..23>
##   p[1].partner  ==> #<markup_tag type='close' name='body' 33..40>
##
## p[2]    ==> #<markup_text type='text' | 24..33>
##   p[2].parent   ==> #<markup_tag type='open' name='body' 6..24>
##   p[2].path     ==> [#<markup_tag type='open' name='html' 0..6>,
##                      #<markup_tag type='open' name='body' 6..24>,
##                      #<markup_text type='text' | 24..33>]
##   p[2].parent.partner.source ==> '</body>'
##
## p[3]    ==> #<markup_tag type='close' name='body' 33..40>
## p[4]    ==> #<markup_tag type='close' name='html' 40..47>
## p[5]    ==> #<markup_object type='eof' | 47..47>

__version__ = "1.039"

import collections, functools, re, sys

# {{ Compatibility definitions 

if sys.version_info[0] < 3:
    def is_string(obj):
        return isinstance(obj, basestring)
    to_char = unichr
    import htmlentitydefs as html_entities
else:
    def is_string(obj):
        return isinstance(obj, str)
    to_char = chr
    import html.entities as html_entities

def is_callable(obj):
    return isinstance(obj, collections.Callable)

# }}

# {{ Exception classes 

class parse_error (Exception):
    pass

class parse_failed (parse_error):
    pass

# }}

# {{ @bounded(meth) 

def bounded(meth):
    """Convert a scanner method taking a starting position and
    returning a tuple of (tag, endpos), so that the resulting method
    returns (tag, startpos, endpos).  Abstracts the common bookkeeping
    for several of the methods of markup_scanner.
    """
    def wrapper(self, start, *args, **kw):
        res = meth(self, start, *args, **kw)
        if res is None:
            raise parse_failed(meth.__name__, start, *args)
        return res[0], start, res[1]

    return functools.update_wrapper(wrapper, meth)

# }}

# {{ @cached(meth) 

def cached(meth):
    """Wrap a method to cache its results."""
    cname = '_' + meth.__name__ + '_cache_'
    def wrapper(self, *args, **kw):
        if not hasattr(self, cname):
            setattr(self, cname, meth(self, *args, **kw))
        return getattr(self, cname)

    return functools.update_wrapper(wrapper, meth)

# }}

# {{ @unescape(meth) 

def unescape(meth):
    """Wrap a method yielding a string that may contain escaped
    entities (e.g., &ldquo;) so that the escaping is removed from the
    string.
    """
    def wrapper(self, *args, **kw):
        value = meth(self, *args, **kw)
        result = replace_entities(self.parser.ENTITY_NAME_MAP, value)
        return result

    return functools.update_wrapper(wrapper, meth)

# }}

# {{ replace_entities(emap, value) 

def replace_entities(emap, value):
    def rep1(m):
        key = m.group('key'); val = m.group(0)
        if key.startswith('#'):
            try: val = to_char(int(key[1:]))
            except ValueError: pass
        else:
            val = emap.get(key, val)
        return val
    return re.sub(r'&(?P<key>#?\w+);', rep1, value)

# }}

# {{ class markup_scanner 

class markup_scanner (object):
    """Implements a permissive lexical analyzer for HTML and
    other similar markup languages.

    Usage:
      s = markup_scanner(input_string)
      for tag, start, end, data in s.scan():
         process(kind, start, end, data)

    The components of each result are:
    kind          -- a string describing what the token is.
    start         -- the starting offset of the token.
    end           -- the offset one past the end of the token.
    data          -- token-specific data, or None.

    The kind values are:
    'eof'         -- end of input.
    'com', 'ucom' -- a comment (unterminated if 'ucom').
    'dir', 'udir' -- a markup directive (e.g., <!DOCTYPE html>).
    'cdata', 'udata' -- a CDATA directive (e.g., <![CDATA[...]]>).
    'open'        -- an opening tag (e.g., <html>).
    'self'        -- a self-delimited tag (e.g., <br />).
    'close'       -- a closing tag (e.g., </body>).
    'text'        -- running text.

    The data values are:
    'open'        -- a dictionary giving tag name and attributes.
    'self'        -- a dictionary giving tag name and attributes.
    'text'        -- a list of entities found in the text.
    'com', 'ucom' -- a dictionary giving content.
    'dir', 'udir' -- a dictionary giving directive name and content.

    Tag names ('name') are given as tuples of (start, end).

    Tag attributes ('attribs') are given as a list of tuples, each
    having one of the following forms:
      ('none', 0, 0)  -- for bare attributes.
      ('name', s, e)  -- for unquoted attribute values.
      ('str', s, e)   -- for quoted attribute values, terminated.
      ('ustr', s, e)  -- for quoted attribute values, unterminated.
    
    All data values not described above will be None.  A string or
    comment value is "terminated" if its end marker occurs before the
    end of input; otherwise it is unterminated.
    """
    def __init__(self, src):
        """Create a new scanner using the string src as input."""
        if not is_string(src):
            raise TypeError("input must be a string")
        self.input = src

    def scan(self, start_pos = 0, **opts):
        """Returns a generator that yields each token found in the input,
        starting at the specified starting offset.  Thread-safe.

        Throws parse_error if for some reason a token could not be consumed
        from the input.  This should not happen under ordinary circumstances.
        """
        end = start_pos
        otag, ostart, oend, odata = '', 0, 0, None
        while True:
            tag, start, end, data = self.parse_one(end, **opts)

            # Fold multiple consecutive text tokens into one.
            if tag == otag == 'text':
                oend = end
                odata.extend(data)
            else:
                if otag:
                    yield otag, ostart, oend, odata
                otag, ostart, oend, odata = tag, start, end, data
            if tag == 'eof':
                break
        if otag:
            yield otag, ostart, oend, odata

    # --- Private methods ----------------------------------------------
    # Conventions:
    # scan_* methods return a tuple of "tag", start, end
    # parse_* methods return a tuple of "tag", start, end, data
    #
    # All methods should return a valid tuple or throw parse_failed.
    # The @bounded decorator can help you keep track of this.

    def get_char(self, p):
        return self.input[p : p + 1]

    @bounded
    def scan_string(self, p):
        t = self.input
        q = t[p]
        p += 1
        while self.get_char(p) not in (q, ''):
            p += 1

        if p < len(t):
            return 'str', p + 1
        else:
            return 'ustr', p # Unterminated string

    @bounded
    def scan_name(self, p, end_marks = ''):
        ig, u, v = self.scan_unquoted(p, '</=' + end_marks)
        return 'name', v

    @bounded
    def scan_unquoted(self, p, end_marks = '', allow_blank = False):
        s = p ; ends = '\x00"\'>' + end_marks

        while True:
            c = self.get_char(p)
            if (not c or
                c in ends or
                c.isspace() or
                ord(c) < 32):
                break
            p += 1

        ok = s <= p if allow_blank else s < p
        if ok:
            return 'unq', p

    @bounded
    def scan_space(self, p):
        while self.get_char(p).isspace():
            p += 1

        return 'ws', p
    
    @bounded
    def scan_literal(self, p, value):
        end = p + len(value)
        if self.input[p:end] == value:
            return 'lit', end

    @bounded
    def scan_entity(self, p):
        while True:
            c = self.get_char(p)
            if c == ';':
                return 'ent', p + 1
            elif not c or not c.isalnum():
                return 'uent', p

            p += 1

    @bounded
    def scan_comment(self, p):
        ig, u, v = self.scan_literal(p, '<!--')

        t = self.input
        while v < len(t):
            if t.startswith('-->', v):
                return 'com', v + 3

            v += 1

        # Unterminated comment
        return 'ucom', v

    def parse_attrib(self, p, **opts):
        ntag, ns, ne = self.scan_name(p)
        vtag, vs, ve = 'none', ne, ne
        try:
            ig, u, v = self.scan_space(ne)
            ig, u, v = self.scan_literal(v, '=')
            ig, u, v = self.scan_space(v)

            if self.get_char(v) in ('"', "'"):
                vtag, vs, ve = self.scan_string(v)
            elif opts.get('allow_unquoted', True):
                end_marks = '=' + opts.get('end_marks', '')
                vtag, vs, ve = self.scan_unquoted(
                    v, end_marks, opts.get('allow_blank', True))
        except parse_failed:
            pass

        return 'attr', p, ve, dict(
            name = (ns, ne),
            value = (vtag, vs, ve))

    def parse_attribs(self, p, **opts):
        data = []
        v = p
        while True:
            ig, u, v = self.scan_space(v)
            try:
                ig, u, v, info = self.parse_attrib(v, **opts)
                data.append((u, v, info))
            except parse_failed:
                break

        return 'attrs', p, v, data

    def parse_starttag(self, p, **opts):
        ig, u, v = self.scan_literal(p, '<')
        ntag, ns, ne = self.scan_name(v)
        atag, atts, atte, data = self.parse_attribs(ne, **opts)
        kind = 'open'

        if self.get_char(atte) == '/':
            kind = 'self'
            atte += 1
        if self.get_char(atte) != '>':
            raise parse_failed("parse_starttag", p)

        return kind, p, atte + 1, dict(
            name = (ns, ne),
            attribs = (atts, atte, data))

    def parse_endtag(self, p, **opts):
        ig, u, v = self.scan_literal(p, '</')
        ntag, ns, ne = self.scan_name(v)
        ig, u, v = self.scan_space(ne)

        if self.get_char(v) != '>':
            raise parse_failed("parse_endtag", p)

        return 'close', p, v + 1, dict(
            name = (ns, ne),
            attribs = (ne, v, []))

    def parse_comment(self, p, **opts):
        tag, ns, ne = self.scan_comment(p)
        cs = p + len('<!--')
        ce = ne if tag == 'ucom' else ne - len('-->')

        return tag, ns, ne, dict(content = (cs, ce))

    def parse_cdata(self, p, **opts):
        ig, ns, ne = self.scan_literal(p, '<![CDATA[')

        t = self.input
        c = ne ; kind = 'udata'
        while not t.startswith(']]>', c):
            if c >= len(t): break
            c += 1
        else:
            kind = 'cdata'

        end = c + len(']]>') if kind == 'cdata' else c
        return kind, p, end, dict(content = (ne, c))

    def parse_directive(self, p, end_mark, **opts):
        # p + 2 to skip past <! or <?
        ig, ns, ne = self.scan_name(p + 2, '?' if '?' in end_mark else '')

        t = self.input
        c = ne ; kind = 'udir'
        while not t.startswith(end_mark, c):
            if self.get_char(c) in ('', '<'): break
            c += 1
        else:
            kind = 'dir'

        end = c + len(end_mark) if kind == 'dir' else c

        return kind, p, end, dict(
            name = (ns, ne),
            content = (ns, c))

    def find_entities(self, p, end):
        data = []

        t = self.input
        c = p
        while c < end:
            if t[c] == '&':
                try:
                    tag, s, e = self.scan_entity(c + 1)
                    if e > s:
                        data.append((tag, c, e))
                        c = e
                except parse_failed:
                    pass
            c += 1

        return data

    def parse_one(self, p, **opts):
        t = self.input
        c = p
        if p >= len(t):
            return 'eof', p, p, None
        elif t[p] == '<':
            np = self.get_char(p + 1)
            try:
                if np == '!':
                    try:
                        return self.parse_comment(p)
                    except parse_failed: pass
                    try:
                        return self.parse_cdata(p)
                    except parse_failed: pass
                    return self.parse_directive(p, '>', **opts)
                elif np == '?':
                    return self.parse_directive(p, '?>', **opts)
                elif np == '/':
                    return self.parse_endtag(p, **opts)
                else:
                    return self.parse_starttag(p, **opts)
            except parse_failed:
                c += 1 # skip past an unconsumed "<"

        # Falling through to here means we're in text data
        while c < len(t) and t[c] != '<':
            c += 1

        return 'text', p, c, self.find_entities(p, c)

# }}

# {{ class named_object 

class named_object (object):
    """A mixin for objects with names that adds .name, .name_start, and
    .name_end properties.

    .name       -- a string giving the name of the object.
    .name_start -- start position of the name in the input.
    .name_end   -- end position of the name in the input.
    """
    def __reprtag__(self):
        return 'name=%r' % self.name

    @property
    def name(self):
        start, end = self.get_object_data()['name']
        return self.parser.get_substring(start, end)

    @property
    def name_start(self):
        return self.get_object_data()['name'][0]

    @property
    def name_end(self):
        return self.get_object_data()['name'][1]

# }}

# {{ class markup_object 

class markup_object (object):
    """Represents a markup object such as a tag, a comment, or a run of text
    discovered by the markup parser.

    Key attributes:
    .type        -- string describing the type of markup object.
    .start       -- offset of the beginning of the object in the source.
    .end         -- offset of the end of the object in the source.
    .source      -- the literal text of the object.
    .csource     -- the source text between this object and its partner.
    .next_obj    -- the next object in the input (or None).
    .prev_obj    -- the previous object in the input (or None).
    .parent      -- the smallest enclosing tag (or None).
    .partner     -- the matching tag (for start/end tags).
    .contents    -- list of objects between this and its partner.
    .children    -- list of contents whose parents are this object.
    .first_child -- first element of .children, or None.
    .siblings    -- list of all the parent's children.
    .first_sib   -- the object's leftmost sibling (or None).
    .next_sib    -- the right sibling of this object (or None).
    .prev_sib    -- the left sibling of this object (or None).
    .path        -- the tag path from the root to this object.
    .linepos     -- the (line, cpos) of this object in the source.
    .linecol     -- the (line, column) of this object in the source.
    .linespan    -- the (start, end) of this object's start line.

    The parent of an object is defined as the closest tag of which the object
    is a child, if any.

    The .partner and .parent attributes are writable; you may set the partner
    or parent of any object to any other object.  The partner relationship need
    not be mutual; object A may have partner B, but B may not have partner A.
    Setting partner to None, or deleting partner, removes the relationship.

    Partner and parent relationships between start/end tags are pre-computed by
    the parser, but you are free to modify them as you wish.

    The .contents are those objects occurring between (but not including) the
    object and its partner; this list is empty for objects with no partner.
    The children are those contents whose parent is the object.  The siblings
    of an object are all the children of its parent.

    The length of an object (according to len) is the length of its source.

    Note: The .linepos gives line and character offsets, while .linecol gives
    line and column numbers.  Column numbers are affected by the parser's tab
    width and line/column number settings.  See markup_parser for details.
    """
    def __init__(self, parser, id):
        self.parser = parser
        self.obj_id = id

    def __reprtag__(self):
        return '|'

    def __repr__(self):
        return '#<%s type=%r %s %d..%d>' % (
            type(self).__name__,
            self.type, self.__reprtag__(),
            self.start, self.end)

    def __str__(self):
        return self.source

    def __len__(self):
        return len(self.source)

    def _decache(self, *keys):
        for key in keys:
            tk = '_' + key + '_cache_'
            if getattr(self, tk, None) is None:
                try: delattr(self, tk)
                except AttributeError: pass

    @property
    def type(self):
        obj = self.parser.get_object(self.obj_id)
        return obj[0]

    @property
    def start(self):
        obj = self.parser.get_object(self.obj_id)
        return obj[1]

    @property
    def end(self):
        obj = self.parser.get_object(self.obj_id)
        return obj[2]

    @property
    def source(self):
        return self.parser.get_substring(self.start, self.end)

    @property
    def csource(self):
        p = self.partner
        if p is not None:
            if p.start > self.end:
                lo, hi = self.end, p.start
            else:
                lo, hi = p.end, self.start
            return self.parser.get_substring(lo, hi)
        else:
            return '' # default, no content

    @property
    def next_obj(self):
        if self.obj_id < len(self.parser) - 1:
            return self.parser.get_wrapper(self.obj_id + 1)
        else:
            return None

    @property
    def prev_obj(self):
        if self.obj_id <= 0:
            return None
        else:
            return self.parser.get_wrapper(self.obj_id - 1)

    @property
    @cached
    def parent(self):
        # This is just one-dimensional breadth-first search, but with an
        # asymmetric stop condition:
        #
        # If we reach the beginning of the input without finding a parent,
        # there's no point looking further toward the end, as we have already
        # tried all the open tags that could surround the target.
        #
        # If we reach the end, however, it's possible there's a one-way pair
        # starting earlier in the input, so we will keep going in that case.
        # Thus, a worst-case for this search is a top-level object near the end
        # of a large text.

        pre = self.obj_id - 1
        post = self.obj_id + 1

        while pre >= 0 or post < len(self.parser):
            if pre >= 0:
                t = self.parser.get_wrapper(pre)
                if (t.type == 'open' and
                    t.contains(self) and
                    (self.partner is None or
                     t.contains(self.partner))):
                    return t
                pre -= 1
            else:
                break
            if post < len(self.parser):
                t = self.parser.get_wrapper(post)
                if (t.type == 'close' and
                    t.contains(self) and
                    (self.partner is None or
                     t.contains(self.partner))):
                    return t.partner
                post += 1

        return None

    @property
    def siblings(self):
        if self.parent is None:
            return list(s for s in self.parser.wrappers
                        if s.parent is None)
        else:
            return self.parent.children

    @property
    def first_sib(self):
        if self.parent is None:
            return next(s for s in self.parser.wrappers
                        if s.parent is None)
        else:
            return self.parent.first_child

    @property
    @cached
    def next_sib(self):
        sibs = self.siblings
        if sibs:
            me = sibs.index(self)
            if me < len(sibs) - 1:
                return sibs[me + 1]
        return None

    @property
    @cached
    def prev_sib(self):
        sibs = self.siblings
        if sibs:
            me = sibs.index(self)
            if me > 0:
                return sibs[me - 1]
        return None

    @property
    def partner(self):
        m = self.parser.matches
        w = self.parser.wrappers
        if self.obj_id in m:
            return w[m[self.obj_id]]
        else:
            return None

    @partner.setter
    def partner(self, other):
        self.parser.set_partner(self.obj_id, other and other.obj_id)

    @partner.deleter
    def partner(self):
        self.parser.set_partner(self.obj_id, None)

    @property
    def contents(self):
        p = self.partner
        if p is not None:
            lo = min(self.obj_id, p.obj_id)
            hi = max(self.obj_id, p.obj_id)
            return list(self.parser.get_wrapper(id)
                        for id in range(lo + 1, hi))

        return [] # default, no contents

    def contains(self, other):
        """As other in self.contents, but doesn't create a list."""
        p = self.partner
        if p is not None:
            left =  self.parser.get_wrapper(min(self.obj_id, p.obj_id))
            right = self.parser.get_wrapper(max(self.obj_id, p.obj_id))

            return left.end <= other.start and other.end <= right.start
        else:
            return False

    @property
    def children(self):
        return list(obj for obj in self.contents
                    if obj.parent is self)

    @property
    def first_child(self):
        for obj in self.contents:
            if obj.parent is self:
                return obj
        else:
            return None

    @property
    def path(self):
        path = []
        cur = self
        while cur is not None:
            path.append(cur)
            cur = cur.parent

        path.reverse()
        return path

    @property
    def linepos(self):
        return self.parser.get_linepos(self.start)

    @property
    def linecol(self):
        return self.parser.get_column(self.start)

    @property
    def linespan(self):
        lnum, _ = self.parser._get_linepos(self.start)
        return self.parser._get_linespan(lnum)

    def find(self, **opts):
        """As markup_parser.find(...) but considering only the contents of the
        object, if any.
        """
        return self.parser.find(search_inside = self, **opts)

    def find_after(self, **opts):
        """As markup_parser.find(...) but considering only objects after this
        object, if any.
        """
        return self.parser.find(search_after = self, **opts)

    def first(self, **opts):
        """As markup_parser.first(...) but considering only the contents of
        this tag, if any.
        """
        return self.parser.first(search_inside = self, **opts)

    def first_after(self, **opts):
        """As markup_parser.first(...) but considering only objects after this
        object, if any.
        """
        return self.parser.first(search_after = self, **opts)

    def last(self, **opts):
        """As markup_parser.last(..) but considering only the contents of this
        tag, if any.
        """
        return self.parser.last(search_inside = self, **opts)

    def get_object_data(self):
        obj = self.parser.get_object(self.obj_id)
        return obj[3]

# }}

# {{ class markup_comment 

class markup_comment (markup_object):
    """Represents an SGML or XML style comment or markup directive.

    Key attributes (in addition to those of markup_object):
    .innersource  -- the source not including the comment markers.
    .inner_start  -- the start position of innersource.
    .inner_end    -- the end position of innersource.
    """
    @property
    def innersource(self):
        start, end = self.get_object_data()['content']
        return self.parser.get_substring(start, end)

    @property
    def inner_start(self):
        return self.get_object_data()['content'][0]

    @property
    def inner_end(self):
        return self.get_object_data()['content'][1]

# }}

# {{ class markup_directive 

class markup_directive (named_object, markup_comment):
    """Represents an SGML or XML style processing directive."""

# }}

# {{ class markup_tag 

class markup_tag (named_object, markup_object):
    """Represents a start tag or self-contained tag, which may have attributes
    associated with it.

    Key attributes (in addition to those of markup_tag):
    .attributes -- a list of markup_attribute objects.

    Attributes may also be accessed as atag['name'] as syntactic sugar for
    atag.getattr(name).
    """
    def __getitem__(self, key):
        return self.getattr(key)

    def __contains__(self, key):
        return key.lower() in self.keys()

    @property
    @cached
    def attributes(self):
        data = self.get_object_data()
        u, v, elts = data['attribs']
        return list(markup_attribute(self.parser,
                                     self.obj_id, p)
                    for p in range(len(elts)))

    @property
    def innersource(self):
        data = self.get_object_data()
        u, v, elts = data['attribs']
        return self.parser.get_substring(u, v)

    @property
    def inner_start(self):
        u, v, elts = self.get_object_data()['attribs']
        return u

    @property
    def inner_end(self):
        u, v, elts = self.get_object_data()['attribs']
        return v

    def keys(self):
        """Return a list of the attribute names defined on this tag."""
        return list(s.name.lower() for s in self.attributes)

    def getattr(self, name, *default):
        """Get the attribute whose name is given.  If absent, and a default
        value is given, the default value is returned; otherwise KeyError is
        raised.
        """
        for attr in self.attributes:
            if attr.name.lower() == name.lower():
                return attr
        else:
            if default:
                return default[0]
            raise KeyError(name)

    def getvalue(self, name, *default):
        """Return the value of the attribute whose name is given.  If absent,
        and a default value is given, the default value is returned; otherwise
        KeyError is raised.
        """
        try:
            return self.getattr(name).value
        except KeyError:
            if default:
                return default[0]
            raise

# }}

# {{ class markup_text 

class markup_text (markup_object):
    """Defines a run of text found in the markup.

    Key attributes (in addition to those of markup_object):
    .entities  -- a list of markup_entity objects found in the text.
    .value     -- as .source, but with entities unescaped.

    A text object supports indexing and having its length taken as if it were a
    string; these operations delegate to the .source property.
    """
    @property
    @cached
    def entities(self):
        data = self.get_object_data()
        return [markup_entity(self.parser,
                              self.obj_id, p)
                for p in range(len(data))]

    @property
    @cached
    @unescape
    def value(self):
        return self.source

    def __getitem__(self, itm):
        return self.source[itm]

# }}

# {{ class markup_datum 

class markup_datum (markup_object):
    """Base class for entities, attributes, and other data that hang
    from other markup objects.

    Key attributes (in addition to those of markup_object):
    .parent   -- the markup object that owns this datum (may be None).
    """
    def __repr__(self):
        return '#<%s tag=%d %s %d..%d>' % (
            type(self).__name__, self.obj_id,
            self.__reprtag__(),
            self.start, self.end)

    def __init__(self, parser, id, index):
        super(markup_datum, self).__init__(parser, id)
        self.obj_index = index

    @property
    def parent(self):
        return self.parser.get_wrapper(self.obj_id)

    def get_item_data(self):
        data = self.get_object_data()
        assert 0 <= self.obj_index < len(data)
        return data[self.obj_index]

# }}

# {{ class markup_entity 

class markup_entity (markup_datum):
    """Represents an escaped entity.

    Key attributes (in addition to those of markup_datum):
    .value   -- the unescaped equivalent of this entity.

    Note that if the entity could not be decoded, its value will be equivalent
    to its source.
    """
    @property
    def start(self):
        kind, u, v = self.get_item_data()
        return u

    @property
    def end(self):
        kind, u, v = self.get_item_data()
        return v

    @property
    def source(self):
        kind, u, v = self.get_item_data()
        return self.parser.get_substring(u, v)

    @property
    @cached
    @unescape
    def value(self):
        return self.source

    @property
    def siblings(self):
        return self.parent.entities

# }}

# {{ class markup_attribute 

class markup_attribute (markup_datum):
    """Represents an attribute defined on a start tag.

    Key attributes (in addition to those of markup_object):
    .name        -- string giving the name of the attribute
    .value       -- string giving the content of the attribute.
    .rawvalue    -- as .value, but leaves entities unescaped.
    .name_start  -- start position of the name in the source text.
    .name_end    -- end position of the name in the source text.
    .value_start -- start position of the value in the source text.
    .value_end   -- end position of the value in the source text.

    Note that the name and value start/end positions are not the same as the
    .start and .end for the overall attribute except in that .name_start will
    usually be the same as .start, and .value_end will usually be the same as
    .end, modulo the removal of quotation marks.
    """
    def __reprtag__(self):
        return 'name=%r' % self.name

    def get_item_data(self):
        data = self.get_object_data()
        u, v, lst = data['attribs']
        assert 0 <= self.obj_index < len(lst)
        return lst[self.obj_index]

    @property
    def start(self):
        u, v, data = self.get_item_data()
        return u

    @property
    def end(self):
        u, v, data = self.get_item_data()
        return v

    @property
    def name(self):
        u, v, data = self.get_item_data()
        start, end = data['name']
        return self.parser.get_substring(start, end)

    @property
    @unescape
    def value(self):
        return self.rawvalue

    @property
    def rawvalue(self):
        u, v, data = self.get_item_data()
        kind, start, end = data['value']
        raw = self.parser.get_substring(start, end)
        if kind == 'str':
            return raw[1:-1] # remove quotation marks
        elif kind == 'ustr':
            return raw[1:]   # remove left quotation mark
        else:
            return raw

    @property
    def name_start(self):
        u, v, data = self.get_item_data()
        start, end = data['name']
        return start

    @property
    def name_end(self):
        u, v, data = self.get_item_data()
        start, end = data['name']
        return end

    @property
    def value_start(self):
        u, v, data = self.get_item_data()
        kind, start, end = data['value']
        return start

    @property
    def value_end(self):
        u, v, data = self.get_item_data()
        kind, start, end = data['value']
        return end

    @property
    def siblings(self):
        return self.parent.attributes

# }}

# {{ class markup_parser 

class markup_parser (object):
    """A tag-soup parser for HTML and other similar markup langauges.
    """
    # A set of tag names that should be considered singular by default, even if
    # they are not syntactically singular.
    SINGULAR_TAGS = set()

    # A map of tag names to sets of tag names.  If an open tag in the set is
    # seen while the key tag is open, the key tag will be implicitly closed
    # before the open tag is processed.
    CLOSED_BY_OPEN = {}

    # A map of tag names to sets of tag names.  If a close tag in the set is
    # seen while the key tag is open, the key tag will be implicitly closed
    # before the close tag is processed.
    CLOSED_BY_CLOSE = {}

    # A set of tag names that should be implicitly closed if the end of input
    # is discovered while the tag is open.
    CLOSED_BY_EOF = set()

    # A map of entity names to values, used when reading attribute values.
    ENTITY_NAME_MAP = dict(amp = '&', lt = '<', gt = '>', quot = '"')

    # Settings for .get_linepos().
    LINE_NUM_BASE = 1    # Lines are numbered from this value.
    COLUMN_NUM_BASE = 0  # Columns are numbered from this value.
    TAB_WIDTH = 8        # Tabs have this width in characters.

    def __init__(self, src = None, **opts):
        """Initialize a new parser with the specified source text.  If the
        source is omitted, input may be given to the .parse() method.
        """
        self.input = None

        if src is not None:
            self.parse(src, **opts)

    def __str__(self):
        return self.input or ''

    def parse(self, src, **opts):
        """Parse the specified source text.  Modifies the internal data
        structures of the parser, discarding any previous state.

        Options:
        skip_white_text -- If true, discard text all-whitespace tokens.
        """
        if not is_string(src):
            raise TypeError("input must be a string")

        self.input = src
        scanner = markup_scanner(src)
        if opts.get('skip_white_text', False):
            self.objects = list(t for t in scanner.scan()
                                if t[0] != 'text' or
                                not src[t[1]:t[2]].isspace())
        else:
            self.objects = list(scanner.scan())
        self.wrappers = self.make_wrappers()
        self.__linepos = []
        self.find_partners()

    def feed(self, src, **opts):
        """Add the specified source text to the existing parse.  Extends the
        internal data structures of the parser.
        """
        if self.input is None:
            self.parse(src, **opts)
        else:
            # Force the scanner to reconsider any trailing text in light of the
            # new data we are about to add.
            for w in self.wrappers:
                w._decache('parent', 'next_sib', 'prev_sib')

            sp = 0
            while self.wrappers:
                if self.wrappers[-1].type in ('text', 'ucom', 'udir'):
                    sp = self.wrappers[-1].start
                    self.wrappers.pop()
                    self.objects.pop()
                else:
                    break

            op = len(self.wrappers)

            self.input += src
            scanner = markup_scanner(self.input)
            self.objects.extend(scanner.scan(start_pos = sp))
            self.wrappers.extend(self.make_wrappers(start_pos = op))
            self.find_partners()

    def find(self, **opts):
        """Returns a generator that produces the objects matching the specified
        criteria, in nondecreasing order of start position.

        Search criteria are specified with keyword arguments chosen from the
        following set.

        type          -- select objects whose object type matches.
                         See markup_scanner for possible values.
        name          -- select objects whose name matches.
        hasattr       -- select tags which have the named attribute.
        hasattrs      -- as hasattr, but with multiple attributes.
        attr          -- select tags whose named attribute(s) match.
        source        -- select objects whose source text matches.
        csource       -- select objects whose csource text matches.
        innersource   -- select objects whose innersource text matches.
        value         -- select text objects whose value matches.
        parent        -- select objects whose parent matches.
        partner       -- select objects whose partner matches.
        predicate     -- f(obj) => bool select objects for which the given
                         function returns a true value.

        The above names may be prefixed with 'not_' to negate the sense of the
        individual comparison described, e.g., 'not_hasattr'.

        match_any     -- if true, at least one criterion must match.
        match_all     -- if true, all criteria must match.
        search_after  -- consider only objects occurring after this object.
        search_before -- consider only objects occurring before this object.
        search_inside -- consider the contents of this object.
        case_matters  -- if true, string comparisons are case sensitive.
        negate        -- if true, negate the sense of each criterion.
        reverse       -- if true, search in reverse order.
        map           -- process each matching object before returning.

        Rules for matching:

        String arguments are compared for equality; such comparisons are
        case-insensitive by default, but can be made case-sensitive by setting
        case_matters to true.

        If a regular expression object is given, its search method is used.

        If a callable object is given, it is passed the comparison value, and
        its return value is converted to a truth value.

        If a sequence of objects are given, each is tried in sequence using the
        above rules, and any match selects the object.

        The 'parent' and 'partner' criteria support only the callable object
        rule; any other object is compared for identity (x is Y).

        For attr, specify (name, expr) to test a single attribute.  For
        multiple attributes, specify a list of (name, expr) tuples or a
        dictionary with name keys and expr values.  The values None and True
        match if the attribute exists, regardless of its value; the value False
        matches if the attribute does not exist.

        By default, all criteria must match.  Setting match_any to true or
        match_all to false means at least one criterion must match.  If you set
        both to true, match_all takes priority.

        If no criteria are specified, all objects are selected when match_all
        is true; otherwise no objects are selected.

        Rules for map:

        If 'map' is a callable object, it is called passing each matched object
        and its return value is given as the output for that object.  If map is
        a string, it will be treated as the name of an attribute to find on
        each matched object.  The value of the attribute will be returned; if
        no such attribute exists, None will be returned.  If map is a set, list
        or tuple of strings, a list or tuple of corresponding attribute values
        will be returned (replaced with None for missing values).
        """
        negate = opts.get('negate', False)
        match_any = opts.get('match_any', negate)
        match_all = opts.get('match_all', not match_any)
        case_matters = opts.get('case_matters', False)
        reverse = opts.get('reverse', False)
        mapper = opts.get('map', lambda t: t)

        if is_callable(mapper):
            do_map = mapper
        elif is_string(mapper):
            def do_map(value):
                return getattr(value, mapper, None)
        elif isinstance(mapper, (list, tuple, set)):
            def do_map(value):
                return type(mapper)(getattr(value, t, None) for t in mapper)
        elif isinstance(mapper, dict):
            def do_map(value):
                return type(mapper)(
                    (t, getattr(value, t, None)) for t in mapper)
        else:
            raise TypeError("Invalid mapping rule: %r" % mapper)

        def gsense(f):
            def w(value, exp):
                if negate: return not f(value, exp)
                else: return f(value, exp)
            return w

        def tsense(f):
            def w(candidate, test_name, test_value):
                if test_name.startswith('not_'):
                    return not f(candidate, test_name[4:], test_value)
                else:
                    return f(candidate, test_name, test_value)
            return w

        @gsense
        def do_match(value, exp):
            if is_string(exp):
                if case_matters:
                    return value == exp
                else:
                    return value.lower() == exp.lower()
            elif hasattr(exp, 'search') and is_callable(exp.search):
                return exp.search(value)
            elif is_callable(exp):
                return bool(exp(value))
            elif exp in (None, True):
                return True  # the attribute exists
            elif exp is False:
                return False # no such attribute

            # If we get here, the only other allowable option is
            # for exp to be a collection of things to try.  If that
            # fails, the TypeError is propagated back to the caller.
            for e in iter(exp):
                if do_match(value, e):
                    return True
            else:
                return False

        all_tests = []
        # Order matters here...

        for key in ('type', 'name', 'hasattr', 'hasattrs', 'attr',
                    'source', 'csource', 'innersource', 'partner', 'parent',
                    'predicate', 'value'):
            for k in (key, 'not_' + key):
                if k in opts: all_tests.append((k, opts[k]))

        # Choose candidates to search
        lo_limit = 0                   # Search no index before this.
        hi_limit = len(self.wrappers)  # Search no index at or after this.
        if 'search_after' in opts:
            lo_limit = opts['search_after'].obj_id + 1
        if 'search_before' in opts:
            hi_limit = opts['search_before'].obj_id
        if 'search_inside' in opts:
            t = opts['search_inside'] ; p = t.partner
            if p is None:
                lo_limit = hi_limit = t.obj_id
            else:
                lo, hi = sorted((t.obj_id, p.obj_id))
                lo_limit = max(lo_limit, lo)
                hi_limit = min(hi_limit, hi)

        candidates = list(self.wrappers[i] for i in range(lo_limit, hi_limit))
        if reverse:
            candidates.reverse()

        @tsense
        def t_property(candidate, test_name, test_value):
            return (hasattr(candidate, test_name) and
                    do_match(getattr(candidate, test_name), test_value))

        @tsense
        def t_associate(candidate, test_name, test_value):
            return (hasattr(candidate, test_name) and
                    test_value(getattr(candidate, test_name))
                    if is_callable(test_value)
                    else getattr(candidate, test_name) is test_value)

        @tsense
        def t_has_attr(candidate, test_name, test_value):
            if test_name == 'hasattr':
                test_value = [test_value]

            if not hasattr(candidate, 'keys'):
                return False

            for tv in test_value:
                for key in candidate.keys():
                    if do_match(key, tv):
                        break
                else:
                    return False
            else:
                return True

        @tsense
        def t_attr_match(candidate, test_name, test_value):
            if not hasattr(candidate, 'getattr'):
                return False
            elif isinstance(test_value, tuple):
                tv = [test_value]
            elif isinstance(test_value, dict):
                tv = test_value.items()
            else:
                raise TypeError("invalid key for attribute match: %s" %
                                test_value)

            for a_name, a_exp in tv:
                try:
                    if not do_match(candidate[a_name].value, a_exp):
                        return False
                except KeyError:
                    if a_exp is not False:
                        return False
            else:
                return True

        @tsense
        def t_predicate(candidate, test_name, test_value):
            return test_value(candidate)

        def t_fail(candidate, test_name, test_value):
            return False

        test_map = dict(
            type            = t_property,
            not_type        = t_property,
            name            = t_property,
            not_name        = t_property,
            hasattr         = t_has_attr,
            not_hasattr     = t_has_attr,
            hasattrs        = t_has_attr,
            not_hasattrs    = t_has_attr,
            attr            = t_attr_match,
            not_attr        = t_attr_match,
            source          = t_property,
            not_source      = t_property,
            csource         = t_property,
            not_csource     = t_property,
            innersource     = t_property,
            not_innersource = t_property,
            value           = t_property,
            not_value       = t_property,
            parent          = t_associate,
            not_parent      = t_associate,
            partner         = t_associate,
            not_partner     = t_associate,
            predicate       = t_predicate,
            not_predicate   = t_predicate,
            )
        for candidate in candidates:
            ok = match_all

            for test_name, test_value in all_tests:
                tfunc = test_map.get(test_name, t_fail)
                ok = tfunc(candidate, test_name, test_value)

                if not match_all and ok: break
                if match_all and not ok: break

            if ok:
                yield do_map(candidate)

    def first(self, **opts):
        """As .find(...), but returns only the first matching result, or throws
        KeyError to indicate nothing was found.

        However, if the option key "default" is defined, its value is returned
        instead of a KeyError being thrown.
        """
        try:
            return next(self.find(**opts))
        except StopIteration:
            if 'default' in opts:
                return opts['default']
            else:
                raise KeyError("no matching objects")

    def last(self, **opts):
        """As .first(...), but returns the last matching result."""
        t = dict(opts); t['reverse'] = True
        return self.first(**t)

    def locate(self, pos):
        """Locate and return the token containing the specified offset into the
        parser's input.  Throws IndexError if pos is out of range.
        """
        for obj in self.wrappers:
            if obj.start <= pos < obj.end:
                for sub in getattr(obj, 'attributes', ()):
                    if sub.start <= pos < sub.end:
                        return sub
                return obj
        else:
            if pos == len(self.input):
                return self.wrappers[-1]
            raise IndexError("position %d out of range" % pos)

    def __len__(self):
        """Returns the number of tokens found in the input."""
        return len(self.wrappers)

    def __getitem__(self, itm):
        """Index into the parser's token list."""
        return self.wrappers[itm]

    def __iter__(self):
        """Iterate over the tokens in nondecreasing order of start position."""
        return iter(self.wrappers)

    def get_substring(self, start, end):
        """Return the substring of the parser's input from start up to but not
        including end.  Negative offsets count from the end of the input.
        """
        return self.input[start:end]

    def get_linecount(self):
        """Return the number of lines in the parser's input."""
        self._update_linetab(len(self.input))
        lcount = len(self.__linepos)
        return lcount - (self.input.endswith('\n'))

    def get_linespan(self, lnum):
        """Return the (start, end) positions of line lnum of the parser's
        input, where lnum is indexed from self.LINE_NUM_BASE.
        """
        return self._get_linespan(lnum - self.LINE_NUM_BASE)

    def _get_linespan(self, lnum):
        """[private] Internal line-span interface, zero-indexed."""
        lcount = self.get_linecount()
        _, q, _ = slice(lnum).indices(lcount)
        if q < 0 or q >= lcount:
            raise IndexError("line number %d not in 0..%d" % (q, lcount))

        start = self.__linepos[q] + 1
        if q < lcount - 1:
            end = self.__linepos[q + 1]
        else:
            end = len(self.input) - 1

        return start, end + 1

    def get_line(self, lnum):
        """Return the text of line lnum of the parser's input, where lnum is
        indexed from self.LINE_NUM_BASE.
        """
        return self._get_line(lnum - self.LINE_NUM_BASE)

    def _get_line(self, lnum):
        """[private] Internal line-fetch interface, zero-indexed."""
        start, end = self._get_linespan(lnum)
        return self.input[start:end]

    def get_linepos(self, pos):
        """Given an integer offset, return a tuple (line, cpos) giving the line
        number and character offset of the character at that position in the
        parser's current input.

        Lines are numbered from self.LINE_NUM_BASE and character offsets are
        numbered from zero. These values can be modified to suit your needs.
        """
        lnum, cnum = self._get_linepos(pos)
        return lnum + self.LINE_NUM_BASE, cnum

    def get_offset(self, lnum, offset):
        """Return the zero-based offset of the character at the specified line
        number and character offset in the input.  Raises IndexError if either
        is out of bounds.

        Lines are numbered from self.LINE_NUM_BASE, character offsets from 0.
        """
        return self._get_offset(lnum - self.LINE_NUM_BASE, offset)

    def _get_offset(self, lnum, offset):
        """[private] Compute file offset from zero-based line index and
        character offset.  Throws IndexError if either is out of bounds.
        """
        start, end = self._get_linespan(lnum)
        length = end - start
        if offset < 0 or offset >= length:
            raise IndexError("offset not in 0..%d" % length)

        return start + offset

    def get_column_offset(self, lnum, colnum):
        """Return the zero-based offset of the character at the specified line and
        column offset in the input.  Raises IndexErorr if either is out of bounds.

        Lines are numbered from self.LINE_NUM_BASE, columns are numbered from
        self.COLUMN_NUM_BASE.
        """
        return self._get_column_offset(lnum - self.LINE_NUM_BASE,
                                       colnum - self.COLUMN_NUM_BASE)

    def _get_column_offset(self, lnum, colnum, **opts):
        """[private] Compute file offset from zero-based line index and column
        offset.  Throws IndexError if either is out of bounds.
        """
        start, end = self._get_linespan(lnum)
        length = end - start
        cpos = self._col2pos(start, colnum, **opts)
        if cpos < 0 or cpos >= length:
            raise IndexError("column out of bounds")

        return start + cpos

    def _update_linetab(self, offset):
        """[private] Update the line-end cache up to the line containing the
        given offset.  Throws IndexError if offset is out of range.
        """
        t = self.input
        if offset < 0 or offset > len(t):
            raise IndexError("position %d not in 0..%d" % (offset, len(t)))

        # self.__linepos[x] caches the offset of EOL for line x + 1.
        # A virtual line is imputed to exist prior to the input ending at
        # offset -1.
        # Lines are indexed internally from zero.
        lpc = self.__linepos
        if not lpc:
            lpc.append(-1)

        # Include all lines prior to offset.
        pos = lpc[-1] + 1
        while pos < offset:
            if t[pos] == '\n':
                lpc.append(pos)
            pos += 1

        # Include the line containing offset, if possible.
        while pos < len(t) and  lpc[-1] < offset:
            if t[pos] == '\n':
                lpc.append(pos)
            pos += 1

    def _get_linepos(self, pos):
        """[private] Compute zero-indexed line number and character offset."""
        t = self.input
        if pos < 0 or pos > len(t):
            raise IndexError("position %d not in 0..%d" % (pos, len(t)))

        lpc = self.__linepos

        # Locate the smallest known line index whose end is at or after p.
        def locate(p):
            self._update_linetab(p)
            lo = 0; hi = len(lpc) - 1
            if lpc[hi] < p:
                return hi

            # Invariant: lpc[lo] < p; lpc[hi] >= p
            while lo + 1 < hi:
                mid = (lo + hi) // 2
                if   lpc[mid] > p: hi = mid
                elif lpc[mid] < p: lo = mid
                else: return mid - 1
            return hi - 1

        lnum = locate(pos)
        start, end = self._get_linespan(lnum)
        cnum = pos - start
        return lnum, cnum

    def get_column(self, pos, **opts):
        """Given an integer offset, return a tuple (line, col) giving the line
        and column number of the character at that position in the parser's
        current input.  Unlike .get_linepos(), this method takes into account
        the behaviour of tab characters.

        Lines are numbered from self.LINE_NUM_BASE, and columns are numbered
        from self.COLUMN_NUM_BASE.

        Options:
        tab_width  -- tab width in characters (default self.TAB_WIDTH).
        tab_type   -- how tabs should be expanded (default 'stop').
          'stop':  tab moves to the next tab stop
          'fixed': tab moves forward TAB_WIDTH positions
        """
        lnum, cnum = self._get_column(pos, **opts)
        return lnum + self.LINE_NUM_BASE, cnum + self.COLUMN_NUM_BASE

    def _pos2col(self, start, cpos, **opts):
        """[private] For the line starting at offset start, convert the
        character offset cpos into a column offset.
        """
        tw = opts.get('tab_width', self.TAB_WIDTH)
        tt = opts.get('tab_type', 'stop')
        if tt == 'fixed':
            def advance(p): return p + tw
        else:
            def advance(p): return tw * ((p + tw) // tw)

        colnum = 0
        while cpos > 0:
            if self.input[start] == '\t':
                colnum = advance(colnum)
            else:
                colnum += 1
            start += 1
            cpos -= 1
        return colnum

    def _col2pos(self, start, colnum, **opts):
        """[private] For the line starting at offset start, convert the column
        offset colnum into a character offset.
        """
        tw = opts.get('tab_width', self.TAB_WIDTH)
        tt = opts.get('tab_type', 'stop')
        if tt == 'fixed':
            def advance(p): return p + tw
        else:
            def advance(p): return tw * ((p + tw) // tw)

        epos = cpos = 0
        while epos < colnum:
            if self.input[start] == '\t':
                epos = advance(epos)
            else:
                epos += 1
            start += 1
            cpos += 1
        return cpos - (epos > colnum)

    def _get_column(self, pos, **opts):
        """[private] Compute zero-indexed line and column positions."""
        lnum, cpos = self._get_linepos(pos)
        start, end = self._get_linespan(lnum)
        return lnum, self._pos2col(start, cpos, **opts)

    # --- Private methods ----------------------------------------------

    # Mapping from token types to representation classes.
    __wmap = {'open':  markup_tag, 'self': markup_tag, 'close': markup_tag,
              'text':  markup_text,
              'dir':   markup_directive, 'udir': markup_directive,
              'com':   markup_comment,   'ucom': markup_comment,
              'cdata': markup_comment,   'udata': markup_comment,
              }
    def make_wrappers(self, start_pos = 0):
        # Build a wrapper object for each token; the end user will see
        # these instead of the tuples.
        wraps = [None] * (len(self.objects) - start_pos)
        pos = start_pos
        while pos < len(self.objects):
            tag, u, v, data = self.objects[pos]

            obj = self.__wmap.get(tag, markup_object)(self, pos)
            wraps[pos - start_pos] = obj
            pos += 1

        return wraps

    def find_partners(self):
        """Identify partners for start and end tags, if possible.  Each end tag
        is matched with the closest matching start tag that has not already
        been matched.  Tags matched in this way are matched symmetrically.

        In addition, a start tag t whose name is in SINGULAR_TAGS will not be
        matched, even if a close tag exists for it.

        In addition, a start tag t will close any open tag u for which t is in
        CLOSED_BY_OPEN[u].

        In addition, an end tag t will close any open tag u for which t is in
        CLOSED_BY_CLOSE[u]

        In addition, EOF will close any open tag t for which t is in
        CLOSED_BY_EOF.

        Tags matched by the latter three rules are asymmetric matches; the open
        tag u has t as a partner, but not vice versa.

        All partnership relationships can be manually overridden by assigning
        to or deleting the .partner property of a given object.  Only tags are
        assigned partners by default, but any object can be given a partner by
        manual assignment.
        """
        # When we find the end of a tag, we preemptively define that tag as the
        # parent of all unclaimed tags inside it, that are either single or
        # properly paired.  This saves an expensive computation later.
        #
        # Unbalanced tags are NOT claimed.
        def parentify(lo, hi, obj):
            for p in range(lo, hi):
                t = self.wrappers[p]

                if (not hasattr(t, '_parent_cache_') and
                    (t.type not in ('open', 'close') or
                     (p in matches and lo <= matches[p] <= hi))):
                    t._parent_cache_ = obj

        queue = [] ; matches = {}
        for pos, obj in enumerate(self.wrappers):
            if (obj.type == 'open' and
                obj.name.lower() not in self.SINGULAR_TAGS):

                # If the new start tag implicitly ends its predecessor, make
                # a one-way link from the predecessor to this tag.
                for q in reversed(range(len(queue))):
                    qpos, qobj = queue[q]
                    if (obj.name.lower() in
                        self.CLOSED_BY_OPEN.get(qobj.name.lower(), ())):
                        matches[qpos] = pos
                        parentify(qpos + 1, pos, qobj)
                        queue.pop(q)

                queue.append((pos, obj))

            elif obj.type == 'close':
                for q in reversed(range(len(queue))):
                    qpos, qobj = queue[q]

                    # If we find the open tag to balance, make a two-way link
                    # between the two, and clear the open tag from the queue.
                    if qobj.name == obj.name:
                        matches[qpos] = pos
                        matches[pos] = qpos
                        parentify(qpos + 1, pos, qobj)
                        queue.pop(q)
                        break

                    # If the ending tag implicitly ends its predecessor, make
                    # a one-way link from the predecessor to this tag.
                    elif (obj.name.lower() in
                          self.CLOSED_BY_CLOSE.get(qobj.name.lower(), ())):
                        matches[qpos] = pos
                        parentify(qpos + 1, pos, qobj)
                        queue.pop(q)

            elif obj.type == 'eof':

                # Close any remaining tags that are still open at end of input
                # and which are deemed worthy of that action.
                for q in reversed(range(len(queue))):
                    qpos, qobj = queue[q]

                    if qobj.name.lower() in self.CLOSED_BY_EOF:
                        matches[qpos] = pos
                        parentify(qpos + 1, pos, qobj)
                        queue.pop(q)

        self.matches = matches

    def get_object(self, id):
        assert 0 <= id < len(self.objects)
        return self.objects[id]

    def get_wrapper(self, id):
        assert 0 <= id < len(self.wrappers)
        return self.wrappers[id]

    def set_partner(self, src_id, dst_id, mutual = False):
        m = self.matches
        if dst_id is None:
            m.pop(src_id, None)
        else:
            m[src_id] = dst_id
            if mutual:
                m[dst_id] = src_id

# }}

# {{ class html_parser 

class html_parser (markup_parser):
    """A specialization of markup_parser that knows some of the tag rules for
    HTML.
    """
    SINGULAR_TAGS = set((
        'br', 'embed', 'hr', 'img', 'input', 'link', 'param'))

    CLOSED_BY_OPEN = {
        'p':     set(('p',)),
        'li':    set(('li',)),
        'dt':    set(('dt', 'dd')),
        'dd':    set(('dt', 'dd')),
        'th':    set(('th', 'td', 'tr')),
        'td':    set(('th', 'td', 'tr')),
        'tr':    set(('tr',)),
        'thead': set(('tbody', 'tfoot')),
        'tbody': set(('tbody', 'tfoot')),
        'head':  set(('body',)),
        }

    CLOSED_BY_CLOSE = {
        'li':    set(('ul', 'ol')),
        'dt':    set(('dl',)),
        'dd':    set(('dl',)),
        'th':    set(('table',)),
        'td':    set(('table',)),
        'tr':    set(('table',)),
        'tbody': set(('table',)),
        'tfoot': set(('table',)),
        'body':  set(('html',)),
        }

    CLOSED_BY_EOF = set(('body', 'html'))

    ENTITY_NAME_MAP = dict(markup_parser.ENTITY_NAME_MAP)
    ENTITY_NAME_MAP.update((k, to_char(v)) for k, v in
                           html_entities.name2codepoint.items())

# }}

__all__ = (
    'markup_scanner', 'markup_parser',

    'markup_object', 'markup_tag', 'markup_text',
    'markup_comment', 'markup_directive',
    'markup_entity', 'markup_attribute',

    'parse_error',
    'html_parser')

# Here there be dragons
