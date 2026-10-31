#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///

import argparse
import getpass
import gettext
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

checkout = Path(__file__).resolve().parent

#: Wikimedia shares bot passwords across its wikis, so one login serves them all.
WIKIMEDIA = ('https://*.wikipedia.org', 'https://commons.wikimedia.org', 'https://www.wikidata.org')

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
parser.add_argument(
    '--age',
    action='store_true',
    help=_(
        'also set up a Wikimedia bot password, encrypted with age and a FIDO2 security key '
        '(see docs/Wikipedia.md)'
    ),
)
args = parser.parse_args()
if args.age and args.dry_run:
    parser.error(_('--age cannot be combined with --dry-run'))
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


def setup_age() -> None:
    """Ask for a bot password, encrypt it with age, and point Git's configuration at it."""
    for program in 'age', 'age-plugin-fido2prf':
        if not shutil.which(program):
            sys.exit(_('error: %s not found on PATH, see docs/Wikipedia.md') % program)

    def home(variable: str, default: str) -> Path:
        return Path(os.environ.get(variable) or Path.home() / default)

    data = home('XDG_DATA_HOME', '.local/share') / 'git-credential-age'
    identity, secret = data / 'identity.txt', data / 'wikimedia.age'
    login_config = home('XDG_CONFIG_HOME', '.config') / 'git' / 'wikimedia.gitconfig'

    def git_config(*config: str | Path, check: bool = True) -> str:
        command = ['git', 'config', *map(str, config)]
        return subprocess.run(
            command, stdout=subprocess.PIPE, text=True, check=check
        ).stdout.strip()

    old_login = git_config('--file', login_config, 'remote.origin.mwLogin', check=False)
    login = input(_('Bot password login (YourName@label) [%s]: ') % old_login) or old_login
    if not login:
        sys.exit(_('error: a login is needed, see Special:BotPasswords'))
    replace = not secret.exists() or input(_('Replace the stored password? [y/N] ')) == 'y'
    password = getpass.getpass(_('Bot password (not echoed): ')) if replace else ''

    data.mkdir(parents=True, exist_ok=True)
    if not identity.exists():
        print(_('Creating a credential on the security key, which asks for its PIN and a touch'))
        generate = ['age-plugin-fido2prf', '-generate', 'git-credential-age']
        identity.write_text(
            subprocess.run(generate, stdout=subprocess.PIPE, text=True, check=True).stdout
        )
    if password:
        print(_('Encrypting the password, which asks for the PIN and a touch again'))
        encrypt = ['age', '-e', '-i', identity, '-o', secret]
        subprocess.run(encrypt, input=password, text=True, check=True)

    login_config.parent.mkdir(parents=True, exist_ok=True)
    git_config('--file', login_config, 'remote.origin.mwLogin', login)
    for wiki in WIKIMEDIA:
        git_config(
            '--global', f'includeIf.hasconfig:remote.*.url:mediawiki::{wiki}/**.path', login_config
        )
        git_config('--global', f'credential.{wiki}.helper', 'age wikimedia')
    request = shlex.quote(f'url=https://de.wikipedia.org/w\\nusername={login}\\n\\n')
    print(_('Done. Check with: %s') % f'printf {request} | git credential fill')


if args.age:
    try:
        setup_age()
    except subprocess.CalledProcessError as error:
        sys.exit(_('error: %s failed') % error.cmd[0])
