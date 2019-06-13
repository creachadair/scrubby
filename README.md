# Scrubby

Scrubby is a simple permissive tag-soup parser for HTML, XML, and other
SGML-like markup languages, written in Python.  Unlike a strict parser,
tag-soup parsers like scrubby do not enforce strict nesting rules, and are not
too picky about the lexical structure of the input.

## Installation

    python setup.py install

## Getting Started

```python
import scrubby

parser = scrubby.html_parser(input)

print("Length of input (characters):", len(parser.input))
print("Number of input tokens:", len(parser))
```

## Lexical Structure

A scrubby parser begins by scanning its input into lexical tokens.  Each token
is one of the following:

1. A comment or markup directive,
2. A data token,
3. A tag, or
4. Running text.

A comment begins with `<!--` and ends with `-->`, and contains everything
between those markers.

A markup directive is a name (and maybe other text) enclosed between `<!` and
`>` or `<?` and `?>` markers.  Apart from the name, the scanner does not do any
interpretation of the contents of a directive.

A data token begins with `<![CDATA[` and ends with `]]>`, and contains
everything between those markers.

A tag is a name (and maybe some attributes) enclosed between `<` and `>`
markers.  If the leading `<` is followed by `/`, it's a *close* tag; or if the
trailing `>` is preceded by `/`, it's a *self-delimiting* tag.  Otherwise, it's
an *open* tag.  Each attribute is a name, or a name and value separated by `=`.
A value is either itself a name, or a quoted string.

The scanner's definition of a "name" is very general: It is any sequence of
characters that are (a) printable, (b) not whitespace, and (c) not end markers.
End markers include `<`, `/`, and `=`.

Anything else is treated as "running text".

Comments, markup directives, and data tokens may be incomplete, if the input
ends before their closing mark is found.  The scanner records when this occurs
by prefixing the type of the token with "u", e.g., "ucom" for unterminated
comments, "udata" for unterminated data, and "udir" for unterminated markup
directives.

## Data Model

A scrubby parser is an instance of `scrubby.markup_parser` or one of its
subclasses.  For HTML use `scrubby.html_parser`, which knows some extra rules
about the standard HTML tags.

Input can be provided when the parser is created, e.g.,

```python
parser = scrubby.html_parser('<html> ... </html>')
```

Or input can be added after creation using

```python
parser.feed('more text here')
```

It is usually more efficient to accumulate the entire string in advance, rather
than parsing it incrementally.

At all times, the complete input string is available as

    parser.input

A scrubby parser behaves as a list of tokens in non-decreasing order of their
starting position in the input string.  The last token is a always a "magic"
EOF marker of zero width, whose start position is just past the last character
of the input.  The total number of tokens found in the input is

    len(parser)

Each token is represented as an instance of type `scrubby.markup_object` or one
of its subclasses.  Each markup object `t` has several useful properties:

* `t.type`      -- a string describing what kind of object it is.

    - `"eof"`     : end of input
    - `"com"`     : a comment, e.g. `<!-- ... -->`
    - `"dir"`     : a markup directive, e.g. `<!DOCTYPE html>` or `<?xml ...?>`
    - `"cdata"`   : a data directive, e.g., `<![CDATA[...]]>`
    - `"open"`    : an opening tag, e.g., `<html>`
    - `"self"`    : a self-delimiting tag, e.g., `<br/>`
    - `"close"`   : a closing tag, e.g., `</html>`
    - `"text"`    : running text

* `t.start`     -- offset of the beginning of the object in the source.
* `t.end`       -- offset of the end of the object in the source.
* `t.source`    -- the literal text of the object (substring of input).
* `t.linepos`   -- the (line, column) of the object in the input.
* `t.next_obj`  -- the next object in order, or None.
* `t.prev_obj`  -- the previous object in order, or None.

A note about the `t.type` values: It's possible for a comment, a markup
directive, or a data directive to remain unclosed all the way to the end of the
input.  If that happens, there are special tags `"ucom"`, `"udir"`, and
`"udata"` that represent an "unclosed comment", "unclosed directive", or
"unclosed data directive" respectively.

A note about start and end positions: All positions are given as zero-based
offsets from the start of parser.input.  A start position is the location of
the first character of the token, and and end position is one position PAST the
last character of the token.  This means you can obtain the source of the
object as

    parser.input[t.start : t.end]

and you can compute its length as

    t_len = t.end - t.start

## Partnership

Each object may have another object as its partner, accessed as

    t.partner

By default, the partner of an object is None; however, the parser attempts to
set the partner relationships for "open" and "close" objects.  The general rule
is that each "open" tag is partnered with the closest following "close" tag
that has the same name, and which is not partnered with some other open tag.

For example
```
                       v----------v
  <p1>...<p1>...<q/>...<r></p1>...</r>...<s>...</p1>
  |      ^----------------^                    |
  +--------------------------------------------+
```

Self-delimiting tags, e.g. `<q/>`, are not assigned partners.  Furthermore,
open tags with no corresponding close, or vice versa, are not assigned partners.

Partnership between matching open/close tags is symmetric; however, partnership
is not required to be symmetric in general.  The scrubby.html_parser generates
asymmetric partnerships for cases like these:

```
  |--------------------------| (symmetric)
  v                +---------v (asymmetric)
  <html><head> ... <body> ...</html>
        +----------^           (asymmetric)
```

In other words, the `<head>` tag is given the `<body>` tag as a partner, and
the `<body>` tag is given the `</html>` tag as a partner, but the `</html>`
tag's partner is the `<html>` tag.

This reflects the widespread convention (and now standard) that an open
`<body>` tag implicitly closes any currently-open `<head>`, and that a closing
`</html>` tag implicitly closes any currently-open `<body>`.  Similarly, an
unclosed `<html>` or `<body>` tag may be partnered with the EOF marker.  These
asymmetric partnership rules are encoded in the `scrubby.html_parser` class,
and can be modified to suit your needs.

### Contents

Each object has a list of contents, possibly empty, accessed as

    t.contents

The contents of an object `t` are all those objects that occur AFTER `t` and
BEFORE `t.partner` in the input.  If `t.partner` is None, the list is empty.

The literal source text spanning the contents of t can be accessed as

    t.csource

### Parents

Each object may potentially have a parent, accessed as

    t.parent

Informally, the parent of an object is the smallest symmetrically partnered
open tag completely containing that object.  So, consider for example,

    <p>xxx<q/><r>yyy</r></p>

Here, `<p>` is the parent of "xxx", `<q/>`, `<r>`, and `</r>`, but *not* of
"yyy", because `<r>` is the parent of "yyy".

The parent of `<p>` and `</p>` in this example is None, because no tag
completely encloses them (tags are not considered to contain themselves).

The parent relationship is slightly more complex in cases where tags are not
properly nested, e.g.,

    <w>...<x>...<y>...</x>...<z>...</y>...</w>

Although `<y>` is completely enclosed between `<x>` and `</x>`, `<x>` is not
its parent, because its symmetric partner `</y>` is *not* between `<x>` and
`</x>`.  On the other hand, `<y>` is the parent of `<z>` because, although
`<z>` is an unclosed tag, it has no partner, and so is fully enclosed by `<y>`
and `</y>`.

For any object `t`, you can obtain the path of objects leading from the root of
the document to that object using

    t.path

The path is a list of objects, ending with t, having the property that for all
i > 0, `t.path[i].parent == t.path[i - 1]`.  In the above example, the path for
`<z>` is `[<w>, <y>, <z>]` and the path for `</y>` is `[<w>, </y>]`.

### Children and Siblings

The children of an object `t` are all those objects `u` in `t.contents` for
which `u.parent == t`.  The list of an object's children is accessed as

    t.children

Note that the list may be empty even if `t.contents` is not.  You can access
the first child of an object `t` as

    t.first_child

If `t` has no children, this will be None.

The siblings of an object t are the members of `t.parent.children`; if
`t.parent` is None, this is defined as empty by fiat.  The list of an object's
siblings (including itself) is accessed as

    t.siblings

You can access the first sibling of an object `t` as:

    t.first_sib

The previous sibling in order is:

    t.prev_sib

The next sibling in order is:

    t.next_sib

Any of these may be None if the object in question does not exist.

## Searching

The structure of the document can be navigated by traversing the objects in the
parser and accessing their `.parent`, `.children`, `.contents`, `.siblings`,
and so forth.  The `scrubby.markup_parser` object also provides a powerful
search facility:

    parser.find(...)

This method returns a generator that yields all the objects matching the
specified criteria, which are given as keyword arguments to the method.

For full documentation, read the comment on `scrubby.markup_parser.find()`.
There is also a convenience method

    parser.first(...)

This has the same syntax as `parser.find()`, but returns the first matching
element instead of returning a generator.

In addition, the `scrubby.markup_object` class provides `.find()` and
`.first()` methods that are equivalent to using the parser's `.find()` and
`.first()` methods with the "search_inside" criterion set.

## Object Types

Several subclasses of `scrubby.markup_object` are defined to handle the various
kinds of objects you encounter in markup.  These add various additional
properties you can use to get information about these objects.

* Comments and Directives (`scrubby.markup_com`)
    - `t.innersource` -- the contents of the comment without the comment markers,
                         e.g., the "foo" in `<!--foo-->`

* Directives (`scrubby.markup_dir`)
    - `t.name`        -- the "name" of the directive, e.g., "xml" in `<?xml ... ?>`
                         or "`DOCTYPE`" in `<!DOCTYPE html public "...">`.

  Directives are also treated as comments.

* Running text (`scrubby.markup_text`)
    - `t.entities`    -- a list of character entities occurring in the text, of type
                         `scrubby.markup_entity`.
    - `t.value`       -- as `t.source`, but tries to decode entities.

* Tags (`scrubby.markup_tag`)
    - `t.name`        -- the name of the tag, e.g, "foo" in `</foo>`.
    - `t.attributes`  -- a list of attributes (of type `scrubby.markup_attribute`).
    - `t.innersource` -- the text of the attribute definitions, e.g.,
                      "` href="blah" nofollow`" in `<a href="blah" nofollow>`.
    - `t.keys()`      -- returns a list of known attribute names.

    A tag with attributes can also be indexed by attribute names, e.g.,

    - `t['attr_name']` ⇒ attribute (or `KeyError`)
    - `t.getattr('attr_name')` ⇒ attribute (or `KeyError`)
    - `t.getattr('attr_name', default)` ⇒ attribute (or default)

* Entities (`scrubby.markup_entity`)
    - `t.value`       -- the decoded equivalent of the entity.
    - `t.siblings`    -- the list of other entities in the same text.

* Attributes (`scrubby.markup_attribute`)
    - `t.name`        -- the attribute's name, e.g., "href" in `<a href="blah">`.
    - `t.value`       -- the attribute's value, e.g., "blah" in `<a href="blah">`.
    - `t.siblings`    -- the list of other attributes on the same tag.

    The `.start` and `.end` for an attribute span the whole definition.

    - To span only the name, use:   `t.name_start`, `t.name_end`
    - To span only the value, use:  `t.value_start`, `t.value_end`

## Scanning

Most of the work of parsing is done by `scrubby.markup_scanner`, which
implements a very permissive lexical scanner for an SGML-like markup langauge.
It does not attempt to be standards-compliant, since the point is to tolerate
markup that might choke a compliant parser.

Usage summary:

```python
s = scrubby.markup_scanner(input)
g = s.scan()
for tag, start, end, data in g:
   do_stuff(tag, start, end, data)
```

It is possible, though unlikely, for scanning to fail; if this occurs, an
exception of type scrubby.parse_error will be thrown.

## License

Copyright (c) 2009-2010 Michael J. Fromberger.  All Rights Reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided under the conditions described in the
LICENSE file.
