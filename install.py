#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///

import argparse
import gettext
import os
import sys
from pathlib import Path

checkout = Path(__file__).resolve().parent

_ = gettext.translation(
    'git-remote-mediawiki',
    os.environ.get('TEXTDOMAINDIR') or checkout / 'locale',
    fallback=True,
).gettext

parser = argparse.ArgumentParser(
    description=_('Link the git-* scripts of this checkout into a directory on PATH.')
)
parser.add_argument(
    'directory',
    nargs='?',
    type=Path,
    default=Path.home() / '.local' / 'bin',
    help=_('defaults to ~/.local/bin'),
)
parser.add_argument(
    '-n',
    '--dry-run',
    action='store_true',
    help=_('only print what would be linked'),
)
args = parser.parse_args()
target = args.directory.expanduser().absolute()

if not args.dry_run:
    target.mkdir(parents=True, exist_ok=True)
for script in sorted(checkout.glob('git-*')):
    link = target / script.name
    print(f'{link} -> {script}')
    if not args.dry_run:
        link.unlink(missing_ok=True)
        link.symlink_to(script)

if str(target) not in os.environ.get('PATH', '').split(os.pathsep):
    print(_('warning: %s is not on PATH; git will not find the commands') % target, file=sys.stderr)
