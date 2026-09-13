#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["mwclient>=0.11"]
# ///

# Copyright (C) 2012
#     Charles Roussel <charles.roussel@ensimag.imag.fr>
#     Simon Cathebras <simon.cathebras@ensimag.imag.fr>
#     Julien Khayat <julien.khayat@ensimag.imag.fr>
#     Guillaume Sasdy <guillaume.sasdy@ensimag.imag.fr>
#     Simon Perrat <simon.perrat@ensimag.imag.fr>
# License: GPL v2 or later

# Usage:
#       ./test-gitmw.py <command> [argument]*
# Execute in terminal using the name of the function to call as first
# parameter, and the function's arguments as following parameters
#
# Example:
#     ./test-gitmw.py "get_page" foo .
# will call <wiki_getpage> with arguments <foo> and <.>
#
# Available functions are:
#     "get_page"
#     "delete_page"
#     "edit_page"
#     "getallpagename"
#     "upload_file"

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import mwclient

SLASH_REPLACEMENT = '%2F'


def die(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def read_config(path):
    """Parse the shell-style test.config file.

    Parsing stops as soon as the variables the wiki address is built from are
    known, since the later entries reference shell variables we cannot expand.
    """
    config = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        line = re.sub(r'#.*', '', line).strip()
        if not line:
            continue
        key, _, value = line.partition('=')
        key, value = key.strip(), value.strip()
        config[key] = value
        if key == 'PORT' or (key == 'LIGHTTPD' and value == 'false'):
            break
    return config


CONFIG = read_config(Path(os.environ['CURR_DIR']) / 'test.config')
WIKI_ADDRESS = f'http://{CONFIG["SERVER_ADDR"]}:{CONFIG["PORT"]}'
WIKI_URL = f'{WIKI_ADDRESS}/{CONFIG["WIKI_DIR_NAME"]}'


def connect():
    """Log the admin user in and return the wiki."""
    parts = urlsplit(WIKI_URL)
    site = mwclient.Site(
        parts.netloc, path=f'{parts.path}/', scheme=parts.scheme, force_login=False
    )
    try:
        site.login(CONFIG['WIKI_ADMIN'], CONFIG['WIKI_PASSW'])
    except mwclient.errors.LoginError as error:
        die(f'getpage: login failed: {error}')
    return site


def query_list(site, list_name, **params):
    """Run a list query, following every continuation."""
    params = {'list': list_name, **params}
    items = []
    while True:
        result = site.api('query', **params)
        items.extend(result.get('query', {}).get(list_name, []))
        continuation = result.get('continue')
        if not continuation:
            return items
        params.update(continuation)


def wiki_getpage(site, args):
    """Fetch a page from the wiki and copy its content into a directory."""
    page = site.pages[args.pagename]
    if not page.exists:
        die('getpage: page does not exist')

    # Replace spaces by underscore in the page name
    pagename = page.name.replace(' ', '_').replace('/', SLASH_REPLACEMENT)
    destination = Path(args.destdir) / f'{pagename}.mw'
    destination.write_text(page.text(), encoding='utf-8')


def wiki_delete_page(site, args):
    """Delete the page with the given name from the wiki."""
    page = site.pages[args.pagename]
    if not page.exists:
        die(f'no page with such name found: {args.pagename}')
    page.delete()


def wiki_editpage(site, args):
    """Create or edit a page.

    If <wiki_append> is 'true', <wiki_content> is appended to the current
    content of the page instead of replacing it.
    """
    page = site.pages[args.wiki_page]

    text = args.wiki_content
    if args.wiki_append == 'true':
        text = f'{page.text()}{text}'

    # Eventually, add this page to a category.
    if args.category is not None:
        text = f'{text}\n [[Category:{args.category}]]'

    page.save(text, summary=args.summary or '')


def wiki_getallpagename(site, args):
    """Write the name of every page of the wiki into all.txt.

    If <category> is given, only the pages belonging to it are listed.
    """
    if args.category is not None:
        pages = query_list(
            site,
            'categorymembers',
            cmtitle=f'Category:{args.category}',
            cmnamespace=0,
            cmlimit=500,
        )
    else:
        pages = query_list(site, 'allpages', aplimit=500)

    Path('all.txt').write_text(
        ''.join(f'{page["title"]}\n' for page in pages), encoding='utf-8'
    )


def wiki_upload_file(site, args):
    """Upload a file to the wiki."""
    with open(args.file_name, 'rb') as handle:
        site.upload(
            file=handle,
            filename=args.file_name,
            description='upload a file',
            comment='upload a file',
            ignore=True,
        )


def build_parser():
    parser = argparse.ArgumentParser(prog='test-gitmw.py')
    commands = parser.add_subparsers(dest='command', required=True)

    get_page = commands.add_parser('get_page')
    get_page.add_argument('pagename')
    get_page.add_argument('destdir')
    get_page.set_defaults(function=wiki_getpage)

    delete_page = commands.add_parser('delete_page')
    delete_page.add_argument('pagename')
    delete_page.set_defaults(function=wiki_delete_page)

    edit_page = commands.add_parser('edit_page')
    edit_page.add_argument('wiki_page')
    edit_page.add_argument('wiki_content')
    edit_page.add_argument('wiki_append', nargs='?')
    edit_page.add_argument('-s', '--summary')
    edit_page.add_argument('-c', '--category')
    edit_page.set_defaults(function=wiki_editpage)

    getallpagename = commands.add_parser('getallpagename')
    getallpagename.add_argument('category', nargs='?')
    getallpagename.set_defaults(function=wiki_getallpagename)

    upload_file = commands.add_parser('upload_file')
    upload_file.add_argument('file_name')
    upload_file.set_defaults(function=wiki_upload_file)

    return parser


def normalize(argv):
    """Accept the ``-s=value`` form the shell tests use, like Getopt::Long."""
    normalized = []
    for arg in argv:
        match = re.fullmatch(r'(-[sc])=(.*)', arg, re.DOTALL)
        if match:
            normalized.extend(match.groups())
        else:
            normalized.append(arg)
    return normalized


def main(argv):
    sys.stderr.reconfigure(encoding='utf-8')
    args = build_parser().parse_args(normalize(argv))
    args.function(connect(), args)


if __name__ == '__main__':
    main(sys.argv[1:])
