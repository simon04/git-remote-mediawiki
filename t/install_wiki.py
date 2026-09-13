#!/usr/bin/env python3
"""Install a MediaWiki on this machine, to test against.

The test suite does not need this: it runs against the stand-in in
fakewiki.py, which needs nothing installed. This script exists so that the
same tests can be run against a real MediaWiki, which is the only way to find
out where the fake has drifted from one.

Needs PHP and lighttpd on the machine. Stdlib only, so:

        ./install_wiki.py install
        ./install_wiki.py delete
"""

import argparse
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

#: This directory, which is where the wiki and its database end up.
TEST_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    """Where the wiki goes and what it is called.

    These were t/test.config, which existed to be sourced by shell.
    """

    #: Name of the web server directory holding the wiki.
    directory: str = 'wiki'
    #: Login and password of the wiki's administrator.
    admin: str = 'WikiAdmin'
    password: str = 'AdminPass1'
    #: Where lighttpd listens.
    host: str = 'localhost'
    port: int = 1234
    #: Which MediaWiki to fetch. See https://www.mediawiki.org/wiki/Download.
    version: str = '1.34.2'
    #: Directories, relative to this one.
    web: Path = TEST_DIR / 'WEB'
    files: Path = TEST_DIR / 'mediawiki'

    @property
    def base_url(self) -> str:
        return f'http://{self.host}:{self.port}'

    @property
    def url(self) -> str:
        return f'{self.base_url}/{self.directory}'

    @property
    def www(self) -> Path:
        return self.web / 'www'

    @property
    def tmp(self) -> Path:
        return self.web / 'tmp'

    @property
    def wiki_root(self) -> Path:
        return self.www / self.directory

    @property
    def downloads(self) -> Path:
        return self.files / 'download'

    @property
    def database(self) -> Path:
        return self.files / 'db'

    @property
    def database_backup(self) -> Path:
        return self.files / 'post-install-db'


# Enough for a wiki: HTML, the assets it references, and uploads.
MIME_TYPES = {
    '.html': 'text/html',
    '.htm': 'text/html',
    '.css': 'text/css',
    '.js': 'text/javascript',
    '.json': 'application/json',
    '.txt': 'text/plain',
    '.xml': 'text/xml',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.ico': 'image/vnd.microsoft.icon',
    '': 'text/plain',
}

# Uploading text files is needed by the media tests.
EXTRA_LOCAL_SETTINGS = """
# Added by install_wiki.py
$wgEnableUploads = true;
$wgFileExtensions[] = 'txt';
"""


def fail(message: str) -> None:
    raise SystemExit(message)


def write_lighttpd_config(settings: Settings) -> Path:
    """Write the lighttpd and PHP configuration, replacing what is there."""
    for directory in (settings.web, settings.tmp, settings.www):
        directory.mkdir(parents=True, exist_ok=True)

    mime = ',\n'.join(f'    "{suffix}" => "{kind}"' for suffix, kind in MIME_TYPES.items())
    configuration = settings.web / 'lighttpd.conf'
    configuration.write_text(
        f'server.document-root = "{settings.www}"\n'
        f'server.port = {settings.port}\n'
        f'server.pid-file = "{settings.tmp / "pid"}"\n'
        'server.modules = ("mod_rewrite", "mod_redirect", "mod_access",\n'
        '                  "mod_accesslog", "mod_fastcgi")\n'
        'index-file.names = ("index.php", "index.html")\n'
        f'mimetype.assign = (\n{mime}\n)\n'
        'fastcgi.server = (".php" => ("localhost" => (\n'
        f'    "socket" => "{settings.tmp / "php.socket"}",\n'
        f'    "bin-path" => "php-cgi -c {settings.web / "php.ini"}"\n'
        ')))\n',
        encoding='utf-8',
    )
    (settings.web / 'php.ini').write_text(
        f"session.save_path = '{settings.tmp}'\n", encoding='utf-8'
    )
    return configuration


def start(settings: Settings) -> None:
    """Start lighttpd, restarting it if it is already up."""
    if (settings.tmp / 'pid').is_file():
        print('Instance already running. Restarting...')
        stop(settings)
    configuration = write_lighttpd_config(settings)
    if subprocess.run(['lighttpd', '-f', str(configuration)], check=False).returncode:
        fail('Could not execute the http daemon lighttpd')


def stop(settings: Settings) -> None:
    """Stop lighttpd, if the pid file says it is running."""
    pid_file = settings.tmp / 'pid'
    if not pid_file.is_file():
        return
    subprocess.run(['kill', pid_file.read_text(encoding='utf-8').strip()], check=False)
    pid_file.unlink(missing_ok=True)


def download(settings: Settings) -> Path:
    """Fetch the MediaWiki tarball, unless it is already here."""
    settings.downloads.mkdir(parents=True, exist_ok=True)
    name = f'mediawiki-{settings.version}.tar.gz'
    archive = settings.downloads / name
    if archive.is_file():
        print(f'Reusing {archive}')
        return archive
    major = settings.version.rsplit('.', 1)[0]
    url = f'https://download.wikimedia.org/mediawiki/{major}/{name}'
    print(f'Downloading {url} ...')
    try:
        with urllib.request.urlopen(url) as response, archive.open('wb') as out:
            shutil.copyfileobj(response, out)
    except OSError as error:
        archive.unlink(missing_ok=True)
        fail(f'Unable to download {url}: {error}')
    return archive


def extract(archive: Path, destination: Path) -> None:
    """Unpack the tarball, dropping its top-level directory."""
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as tar:
        members = []
        for member in tar.getmembers():
            _, separator, rest = member.name.partition('/')
            if not separator or not rest:
                continue
            member.name = rest
            members.append(member)
        tar.extractall(destination, members=members, filter='data')
    print(f'Extracted into {destination}')


def install_mediawiki(settings: Settings) -> None:
    """Run MediaWiki's own installer, then keep a copy of the database."""
    local_settings = settings.wiki_root / 'LocalSettings.php'
    if local_settings.is_file():
        fail(f'{local_settings} exists; run "delete" first')

    for directory in (settings.database, settings.database_backup):
        shutil.rmtree(directory, ignore_errors=True)
        directory.mkdir(parents=True)

    installer = settings.wiki_root / 'maintenance' / 'install.php'
    print(f'Installing MediaWiki using {installer}. This may take some time ...')
    completed = subprocess.run(
        [
            'php',
            str(installer),
            '--server',
            settings.base_url,
            f'--scriptpath=/{settings.directory}',
            '--lang',
            'en',
            '--dbtype',
            'sqlite',
            '--dbpath',
            str(settings.database),
            '--pass',
            settings.password,
            'Git-MediaWiki-Test',
            settings.admin,
        ],
        check=False,
    )
    if completed.returncode:
        fail(f'{installer} failed, see above. Try "delete" first.')

    with local_settings.open('a', encoding='utf-8') as settings_file:
        settings_file.write(EXTRA_LOCAL_SETTINGS)

    shutil.copytree(settings.database, settings.database_backup, dirs_exist_ok=True)


def install(settings: Settings) -> None:
    """Put a wiki in the web server's directory."""
    start(settings)
    extract(download(settings), settings.wiki_root)
    install_mediawiki(settings)
    print(f'Your wiki has been installed. You can check it at\n\t{settings.url}')


def reset(settings: Settings) -> None:
    """Put the database back as it was just after installation."""
    if not settings.database_backup.is_dir():
        fail(f'No backup database at {settings.database_backup}; not installed yet?')
    shutil.rmtree(settings.database, ignore_errors=True)
    shutil.copytree(settings.database_backup, settings.database)
    print(f'{settings.database} has been reset')


def delete(settings: Settings) -> None:
    """Remove the wiki and everything it stored."""
    stop(settings)
    for directory in (settings.web, settings.database, settings.database_backup):
        shutil.rmtree(directory, ignore_errors=True)


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog='install_wiki.py',
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    defaults = Settings()
    parser.add_argument('--port', type=int, default=defaults.port, help='port to serve on')
    parser.add_argument(
        '--mediawiki-version', default=defaults.version, help='which MediaWiki to fetch'
    )
    parser.add_argument('--admin', default=defaults.admin, help="the wiki administrator's name")
    parser.add_argument('--password', default=defaults.password, help='and their password')
    commands = {
        'install': install,
        'delete': delete,
        'reset': reset,
        'start': start,
        'stop': stop,
    }
    parser.add_argument(
        'command', choices=commands, metavar='<command>', help=f'one of: {", ".join(commands)}'
    )
    args = parser.parse_args(argv)

    commands[args.command](
        Settings(
            port=args.port, version=args.mediawiki_version, admin=args.admin, password=args.password
        )
    )


if __name__ == '__main__':
    main(sys.argv[1:])
