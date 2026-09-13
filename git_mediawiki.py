"""Shared helpers for the Git-MediaWiki bridge.

This module is imported by the ``git-remote-mediawiki`` and ``git-mw``
scripts, which declare the ``mwclient`` dependency in their PEP 723
inline metadata; it is not meant to be run on its own.
"""

import io
import logging
import re
import subprocess
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlsplit

import mwclient
import requests
from mwclient.errors import APIError, MwClientError

# Totally unstable API.
VERSION = '0.01'

# Mediawiki filenames can contain forward slashes. This variable decides by
# which pattern they should be replaced.
SLASH_REPLACEMENT = '%2F'

# HTTP codes
HTTP_CODE_OK = 200
HTTP_CODE_PAGE_NOT_FOUND = 404

# POSIX NAME_MAX. Used to keep the on-disk file names short enough.
NAME_MAX = 255

# Errors raised while talking to a wiki. Everything mwclient raises derives
# from MwClientError, and the requests exceptions below it derive from OSError.
WIKI_ERRORS = (MwClientError, OSError)

# A decoded MediaWiki API response. The API is schemaless enough, and the
# bridge reaches into few enough corners of it, that spelling out the shapes
# would be more fiction than documentation.
type ApiResult = dict[str, Any]

__all__ = [
    'HTTP_CODE_OK',
    'HTTP_CODE_PAGE_NOT_FOUND',
    'VERSION',
    'WIKI_ERRORS',
    'APIError',
    'MediaWiki',
    'clean_filename',
    'connect',
    'git_config',
    'git_config_all',
    'git_config_bool',
    'git_credential',
    'logger',
    'revision_content',
    'run_git',
    'run_git_bytes',
    'smudge_filename',
]

# Progress reports and diagnostics go to stderr, where Git relays them to the
# user without mixing them into the fast-import stream.
logger = logging.getLogger('git-mediawiki')


############################### Git helpers ###################################


def run_git_bytes(args: Sequence[str], *, quiet: bool = False) -> bytes:
    """Run ``git`` with ``args`` and return its standard output as bytes.

    A non-zero exit status is not an error: callers inspect the (possibly
    empty) output instead. ``quiet`` discards git's own diagnostics.
    """
    return subprocess.run(
        ['git', *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL if quiet else None,
        check=False,
    ).stdout


def run_git(args: Sequence[str], *, quiet: bool = False) -> str:
    """Run ``git`` with ``args`` and return its standard output as text."""
    return run_git_bytes(args, quiet=quiet).decode('utf-8', 'replace')


def git_config(name: str) -> str:
    """Return the value of the ``name`` configuration variable, or ''."""
    return run_git(['config', '--get', name], quiet=True).strip()


def git_config_bool(name: str, default: bool = False) -> bool:
    """Return the ``name`` configuration variable as a boolean.

    ``default`` is what an unset variable means, so a setting that is on
    unless it is explicitly turned off reads as ``default=True``.
    """
    value = run_git(['config', '--get', '--bool', name], quiet=True).strip()
    return default if not value else value == 'true'


def git_config_all(name: str) -> list[str]:
    """Return every value of the multi-valued ``name`` configuration variable.

    Accept both space-separated values and multiple keys in the config file.
    Spaces should be written as ``_`` anyway, since we split on whitespace.
    """
    return run_git(['config', '--get-all', name], quiet=True).split()


def git_credential(
    credential: dict[str, str], operation: str = 'fill'
) -> dict[str, str]:
    """Run ``git credential <operation>`` on a credential description.

    For ``fill`` the credential completed by Git is returned, for ``approve``
    and ``reject`` the input is returned unchanged.
    """
    for key, value in credential.items():
        if value and ('\n' in value or '\0' in value):
            raise ValueError(f'invalid credential value for {key}')

    request = ''.join(
        f'{key}={value}\n' for key, value in credential.items() if value
    )
    process = subprocess.run(
        ['git', 'credential', operation],
        input=f'{request}\n',
        stdout=subprocess.PIPE if operation == 'fill' else subprocess.DEVNULL,
        encoding='utf-8',
        check=True,
    )
    if operation != 'fill':
        return credential

    filled = dict(credential)
    for line in process.stdout.splitlines():
        if not line:
            break
        key, _, value = line.partition('=')
        filled[key] = value
    return filled


############################# Filename mangling ###############################


def clean_filename(filename: str) -> str:
    """Turn a Git file name into the corresponding MediaWiki page name."""
    filename = filename.replace(SLASH_REPLACEMENT, '/')
    # [, ], |, {, and } are forbidden by MediaWiki, even URL-encoded.
    # Do a variant of URL-encoding, i.e. looks like URL-encoding, but with _
    # added to prevent MediaWiki from thinking this is an actual special
    # character.
    return re.sub(
        r'[\[\]{}|]', lambda match: f'_%_{ord(match.group()):x}', filename
    )


def smudge_filename(filename: str) -> str:
    """Turn a MediaWiki page name into the corresponding Git file name."""
    filename = filename.replace('/', SLASH_REPLACEMENT).replace(' ', '_')
    # Decode forbidden characters encoded in clean_filename
    filename = re.sub(
        r'_%_([0-9a-fA-F][0-9a-fA-F])',
        lambda match: chr(int(match.group(1), 16)),
        filename,
    )
    return filename[: NAME_MAX - len('.mw')]


############################# MediaWiki access ################################


class MediaWiki:
    """Thin wrapper around :class:`mwclient.Site`.

    It exposes the handful of raw-API operations the bridge needs, so that the
    calling code can keep speaking in terms of MediaWiki API queries.
    """

    def __init__(self, url: str) -> None:
        self.url = url.rstrip('/')
        parts = urlsplit(self.url)
        path = parts.path
        if not path.endswith('/'):
            path += '/'
        self.site = mwclient.Site(
            parts.netloc,
            path=path,
            scheme=parts.scheme or 'http',
            clients_useragent=f'git-mediawiki/{VERSION} (https://github.com/Git-Mediawiki/Git-Mediawiki)',
            force_login=False,
        )

    @property
    def session(self) -> requests.Session:
        """The underlying HTTP session, shared with the API calls."""
        return self.site.connection

    def api(self, action: str, **params: Any) -> ApiResult:
        """Perform an API call and return the decoded JSON response."""
        return self.site.api(action, **params)

    def query(self, **params: Any) -> ApiResult:
        """Perform an ``action=query`` API call."""
        return self.site.api('query', **params)

    def query_list(self, list_name: str, **params: Any) -> list[ApiResult]:
        """Run a list query, following every continuation."""
        params = {'list': list_name, **params}
        items = []
        while True:
            result = self.site.api('query', **params)
            items.extend(result.get('query', {}).get(list_name, []))
            continuation = result.get('continue')
            if not continuation:
                return items
            params.update(continuation)

    def login(self, username: str, password: str, domain: str | None = None) -> None:
        """Log in, raising :class:`mwclient.errors.LoginError` on failure."""
        self.site.login(username, password, domain=domain or None)

    def edit(self, **params: Any) -> ApiResult:
        """Perform an ``action=edit`` API call with a fresh CSRF token."""
        return self.api('edit', token=self.site.get_token('edit'), **params)

    def delete(self, **params: Any) -> ApiResult:
        """Perform an ``action=delete`` API call with a fresh CSRF token."""
        return self.api('delete', token=self.site.get_token('delete'), **params)

    def upload(self, filename: str, content: bytes, comment: str) -> ApiResult:
        """Upload ``content`` as the media file ``filename``."""
        return self.site.upload(
            file=io.BytesIO(content),
            filename=filename,
            description=comment,
            comment=comment,
            ignore=True,
        )

    def get_page(self, title: str) -> ApiResult | None:
        """Return the page information merged with its latest revision."""
        result = self.query(
            prop='revisions',
            rvprop='content|timestamp|ids|comment|user',
            titles=title,
        )
        pages = result.get('query', {}).get('pages', {})
        if not pages:
            return None
        page = next(iter(pages.values()))
        revisions = page.get('revisions')
        if revisions:
            page = {**page, **revisions[0]}
        return page


def revision_content(revision: ApiResult) -> str | None:
    """Return the wikitext of ``revision``, or None for a suppressed one.

    MediaWiki 1.32 moved the content into a "main" slot; both layouts are
    accepted so that the bridge keeps working with older wikis.
    """
    slots = revision.get('slots')
    if slots:
        return slots.get('main', {}).get('*')
    return revision.get('*')


def connect(remote_name: str, remote_url: str) -> MediaWiki:
    """Connect to ``remote_url``, logging in if the remote is configured for it."""
    wiki_login = git_config(f'remote.{remote_name}.mwLogin')
    wiki_password = git_config(f'remote.{remote_name}.mwPassword')
    wiki_domain = git_config(f'remote.{remote_name}.mwDomain')

    wiki = MediaWiki(remote_url)
    if not wiki_login:
        return wiki

    credential = git_credential(
        {'url': remote_url, 'username': wiki_login, 'password': wiki_password}
    )
    try:
        wiki.login(credential['username'], credential['password'], wiki_domain)
    except WIKI_ERRORS as error:
        logger.warning(
            f'Failed to log in mediawiki user "{credential["username"]}" on {remote_url}'
        )
        logger.warning(f'  (error {error})')
        git_credential(credential, 'reject')
        raise SystemExit(1) from error

    git_credential(credential, 'approve')
    logger.warning(f'Logged in mediawiki user "{credential["username"]}".')
    return wiki
