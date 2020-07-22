##
## Name:     scrubbyex.py
## Purpose:  Cookbook examples for the tag-soup parser defined in scrubby.py
##
## Copyright (C) 2009, Michael J. Fromberger, All Rights Reserved.
##
## The examples in this file are intended to serve as an executable
## tutorial for how to use the library.  The examples are intended to
## be followed in consecutive fashion, and later examples will not
## generally explain things covered by the earlier ones.

from __future__ import print_function
import scrubby
import os, re, sys

# For compatibility with Python 2 and 3.
try:
    import urllib.request as urllib
except ImportError:
    import urllib

# {{ Utility functions

# These are some utility functions that are used by the examples further along
# in this file.


def load_url(url):
    """Load the document at the specified URL."""
    u = urllib.urlopen(url)
    try:
        return u.read()
    finally:
        u.close()


def untabify(text, width):
    """Replace tabs with spaces in text."""
    def next_stop(p):
        return width * ((p + width) // width)

    def pad(p):
        return ' ' * (next_stop(p) - p)

    out = list(text)
    pos = 0
    for cur, c in enumerate(out):
        if c == '\t':
            out[cur] = pad(pos)
            pos += len(out[cur])
        elif c == '\n':
            pos = 0
        else:
            pos += 1

    return ''.join(out)


def format_snippet(obj, prefix='', span=False, **opts):
    """Print a descriptive snippet for the given object."""
    width = opts.get('width', 0)
    tsize = opts.get('tabsize', 8)
    lnum, cnum = obj.linecol
    line = untabify(obj.parser.get_line(lnum).rstrip(), tsize)
    if width and len(line) > width:
        line = line[:width]

    if span:
        lead = ' ' * cnum + '~' * len(obj.source)
    else:
        lead = '-' * cnum + '^'

    if width and len(lead) > width:
        lead = lead[:width - 1] + '>'

    mark = prefix + lead
    return (prefix + line + '\n' + mark)


# }}

# This variable is global so that you can inspect the guts of the parser after
# one of the demo functions has set it up.
parser = None

# {{ report_missing_alts(url)


#<>
def report_missing_alts(url):
    """<> Generate a report of the image tags that lack an ALT attribute in an
    HTML document.
    """
    print("report_missing_alts(%r)" % url)

    global parser

    # The master parser class is markup_parser.  To parse, either pass a string
    # to the constructor, use the .parse() method after the parser object is
    # created.  Input is parsed as soon as it becomes available.  The
    # html_parser class is a subclass of markup_parser that has some special
    # knowledge of HTML structure.
    parser = scrubby.html_parser(load_url(url).decode('utf8'))

    # The .find(...) and .first(...) methods of the markup_parser object are
    # the primary means for locating things in a parsed document.  Here, we
    # begin by finding <img> tags that have a src attribute but no alt.

    # The .find() method takes keyword arguments that specify search criteria.
    # If no criteria are given, every object in the source is returned, in
    # nondecreasing order of start position.
    #
    # The attr predicate can accept a list of (name, value) or a dictionary of
    # name:value mappings to compare.
    #
    # Usually, the values would be strings, regular expressions, or functions
    # to do value comparison.  But, True and False are treated specially: A
    # match value of True accepts as long as the attibute is defined,
    # regardless of content.  A match value of False accepts if the attribute
    # is undefined.  Each individual attribute condition must hold for the
    # attr to succeed.

    for img in parser.find(name='img', attr={'src': True, 'alt': False}):

        # Every object returned by the parser has a .linepos attribute.  When
        # read, this computes the 1-based line and column offsets of the
        # starting position of the object.
        ln, cn = img.linepos

        print("Missing ALT on IMG at %(line_num)s, column %(col_num)s:\n"
              "\t%(tag)s" % dict(line_num=ln, col_num=cn, tag=img.source))

    print("<done>")


# }}

# {{ report_unclosed_paras(url)


#<>
def report_unclosed_paras(url):
    """<> Generate a report of any <p> tags that are not balanced by a
    corresponding </p> in an HTML document.
    """
    print("report_unclosed_paras(%r)" % url)

    global parser
    parser = scrubby.html_parser(load_url(url).decode('utf8'))

    # The markup_parser distinguishes several types of objects: Tags, markup
    # directives, running text, and comments.  Each of these objects is
    # represented by an instance of markup_object or one of its subclasses.

    # Every object has a read-only .type attribute that contains a string
    # describing what the object is.  Open tags (e.g., <p>) have an type of
    # "open", which distinguishes them from close tags (e.g., </p>) and XML
    # style self-delimiting tags (e.g., <br/>).

    # Predictably, close tags have a type of "close", and self-tags have a type
    # of "self".

    for p in parser.find(name='p', type='open'):
        ln, cn = p.linepos  # see report_missing_alts(...)

        # Each tag may potentially have a "partner", accessed via its
        # .partner attribute, which defines its scope within the source.
        # The parser attempts to match end tags with start tags, and
        # assign each tag a partner.

        if p.partner is None:
            print("Mismatched <P> tag "
                  "at line %(line_num)s, column %(col_num)s" %
                  dict(line_num=ln, col_num=cn))

        # Of course, it's possible that no matching tag will be found.
        # When that happens, the parser tries a few simple rules to
        # limit the scope of tags.  The partner of a correctly-matched
        # start tag should be an end tag with the same name; if it's not,
        # we're seeing an example of the parser's ad-hoc rules in action.

        elif (p.partner.type != 'close' or p.partner.name.lower() != 'p'):

            pln, pcn = p.partner.linepos

            print(
                "Mismatched <P> tag at line %(line_num)s, column %(col_num)s\n"
                " implicitly closed by %(closer)s"
                " at line %(partner_line_num)s, column %(partner_col_num)s" %
                dict(line_num=ln,
                     col_num=cn,
                     partner_line_num=pln,
                     partner_col_num=pcn,
                     closer=p.partner.source))

    print("<done>")


# }}

# {{ report_explicit_styles(url)


def report_explicit_styles(url):
    """<> Generate a report of any non-SPAN tags that have a non-empty explicit
    style attribute.  This can catch things which probably should have been put
    into a stylesheet.
    """
    global parser
    parser = scrubby.html_parser(load_url(url).decode('utf8'))

    # More complex matches can be computed by a matching function, which takes
    # the object to be matched and returns true/false.
    def is_nonempty(v):
        return v.strip() != ''

    # Comparison keys can take multiple values, such as type in this example.
    # This will match any object whose type is one of the specified values.
    #
    # For matching keys such as attr, you can compare to a string, or to a
    # callable function; in the latter case, the function is called with the
    # attribute value, and if it returns a true value, the attribute is
    # considered to match.  In fact, any place where you can provide a string
    # to compare, you can also provide a function like this.
    #
    # Note that the name of a comparison key, such as "name", can be prefixed
    # with "not_" to invert the sense of the comparison.

    for p in parser.find(type=('open', 'self'),
                         attr=('style', is_nonempty),
                         not_name='span'):
        ln, cn = p.linepos  # see report_missing_alts(...)

        print(
            "Tag <%(name)s> has an explicit style "
            "at line %(line_num)s, column %(col_num)s\n"
            "%(style)s" %
            dict(line_num=ln,
                 col_num=cn,
                 name=p.name,
                 style=format_snippet(
                     p['style'], prefix='| ', span=True, width=80, tabsize=8)))

    print("<done>")


# }}

# {{ fetch_latest_comic()


def fetch_latest_comic():
    """<> Demonstrates some simple screen scraping techniques, by downloading
    the latest image from the "Looking for Group" web comic.

    Check out LFG at <http://www.lfgcomic.com/>.
    """
    print("fetch_latest_comic()")

    global parser

    url = 'http://www.lfgcomic.com/page/latest'
    print("Loading: <%s>" % url)
    parser = scrubby.html_parser(load_url(url).decode('utf8'))

    # The <img> tag containing the comic is the first image found
    # inside the "comic" division.

    # So, first we'll find the earliest <div> tag with id="comic".
    # If we don't find one, this will throw KeyError.
    #
    # The .first(...) method is like .find(...), but returns only the
    # first matching object, rather than a generator for all of them.
    cdiv = parser.first(name='div', attr=('id', 'comic'))

    # Now, we'll search "inside" that tag for the first <img>.  The
    # contents of a tag are defined as all those objects between the
    # tag and its partner, not including the tag itself.  The .first()
    # and .find() methods of markup_tag are just wrappers for the
    # parser's .first() and .find() methods, which supply the
    # search_inside keyword argument in addition to whatever else you
    # provide.
    image = cdiv.first(name='img')

    # Now we can just extract the source and grab the image.  Start
    # and self tags behave like dictionaries with respect to their
    # attributes: tag.keys() returns a list of attibute names defined
    # on the tag, and tag['attrname'] returns a markup_attribute
    # object that represents the attribute.  The .value of an
    # attribute object gives the text of the value as defined in the
    # source file.
    src = image['src'].value

    print("Loading: <%s>" % src)
    image_data = load_url(src)

    file_name = os.path.basename(src)

    print("Saving: %s" % file_name)
    with open(file_name, 'wb') as fp:
        fp.write(image_data)

    print("<done>")


# }}

# Here there be dragons.
