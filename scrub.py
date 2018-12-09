#!/usr/bin/env python
##
## Name:     scrub.py
## Purpose:  Wrapper script to examine a web page's source with scrubby.
##
## Copyright (C) 2009, Michael J. Fromberger, All Rights Reserved.
## 
## Just load up the data, create a parser, and drop into interactive mode.
##
from __future__ import print_function
import code, getopt, os, scrubby, sys, urlparse
try:
    from urllib import urlopen
except ImportError:
    from urllib.request import urlopen

def usage(opts):
    print("Usage: scrub.py [options] <url>", file=sys.stderr)
    if opts:
        print("\nOptions:\n"
              "  -e/--encoding <enc>  : specify input encoding.\n"
              "  -h/--html            : treat input as HTML.\n"
              "  -s/--skipwhite       : skip whitespace text runs.\n"
              "  --help               : print this help message.\n",
              file=sys.stdout)
        return 0
    else:
        print("  [use --help for a summary of options]", file=sys.stderr)
        return 1

def main(argv):
    opt_encoding = 'utf-8'
    opt_html = False
    opt_skipwhite = False
    try:
        opts, args = getopt.getopt(
            argv, 'e:hs', ('encoding=', 'help', 'html', 'skipwhite'))
    except getopt.GetoptError:
        _, e, _ = sys.exc_info()
        print("Error: %s" % e)
        return usage(False)

    # Interpret command-line options.
    for opt, arg in opts:
        if opt in ('-e', '--encoding'):
            opt_encoding = arg
        elif opt in ('-h', '--html'):
            opt_html = True
        elif opt in ('-s', '--skipwhite'):
            opt_skipwhite = True
        elif opt == '--help':
            return usage(True)

    if not args:
        return usage(False)

    # Load data from the specified address.
    u = urlopen(args[0])
    if u.code is None or u.code == 200:
        data = u.read()
        print("- Read %d byte%s from %s" % (
            len(data), "" if len(data) == 1 else "s", u.url))
    else:
        print("Error %s reading %s" % (
            u.code, u.url))
        return 1

    # Summarize options, set up interactive environment.
    print("- encoding:  %s\n"
          "- html:      %s\n"
          "- skipwhite: %s" % (opt_encoding, opt_html, opt_skipwhite))
    cls = scrubby.html_parser if opt_html else scrubby.markup_parser
    p = cls(data.decode(opt_encoding), skip_white_text=opt_skipwhite)

    env = {'__name__': '__console__',
           '__doc__': None,
           'p': p,
           'url': u.url,
           'data': data,
           'urlparse': urlparse}

    print()
    code.interact(banner = '--- Entering interactive mode', local=env)
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

# Here there be dragons
