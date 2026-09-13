"""An in-process stand-in for a MediaWiki ``api.php``.

The tests drive the real ``git-remote-mediawiki`` against this, so that the
suite needs no PHP, no web server and no MediaWiki install.

Only what the bridge actually asks for is implemented. Anything else answers
with an API error rather than a plausible-looking empty result, so that a gap
in the fake shows up as a failing test instead of as a passing one: a fake that
guesses is worse than no fake, because it gives confidence that is not earned.
"""

import json
import re
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

# Namespace ids, as MediaWiki numbers them.
NAMESPACES = {
    '': 0,
    'Talk': 1,
    'User': 2,
    'Project': 4,
    'File': 6,
    'Help': 12,
    'Category': 14,
}

# What this wiki claims to accept as an upload.
FILE_EXTENSIONS = ['txt', 'png', 'jpg', 'gif', 'svg']


def normalise_title(title: str) -> str:
    """Normalise a title the way MediaWiki does.

    Underscores become spaces and the first letter of the page name is
    capitalised, which is why editing "foo" gives you a page called "Foo".
    """
    title = title.replace('_', ' ').strip()
    prefix, separator, name = title.partition(':')
    if separator and prefix in NAMESPACES:
        return f'{prefix}:{name[:1].upper()}{name[1:]}'
    return f'{title[:1].upper()}{title[1:]}'


@dataclass
class Revision:
    """One revision of one page. ``text`` of None stands for a suppressed one."""

    revid: int
    user: str
    timestamp: str
    comment: str
    text: str | None


@dataclass
class Page:
    """A page and its revisions, newest last."""

    pageid: int
    title: str
    revisions: list[Revision] = field(default_factory=list)
    upload: bytes | None = None

    @property
    def namespace(self) -> int:
        prefix, separator, _ = self.title.partition(':')
        return NAMESPACES.get(prefix, 0) if separator else 0

    @property
    def text(self) -> str:
        return self.revisions[-1].text or ''

    def links(self, prefix: str) -> list[str]:
        """Titles of the ``prefix:`` links in the current text, e.g. File:."""
        return [f'{prefix}:{name}' for name in re.findall(rf'\[\[{prefix}:([^\]]+)\]\]', self.text)]


class FakeWiki:
    """A MediaWiki that lives in this process.

    Tests change its contents through the methods here rather than over HTTP;
    only the code under test goes through the server.
    """

    def __init__(self) -> None:
        self.pages: dict[int, Page] = {}
        self.next_pageid = 1
        self.next_revid = 1
        self.username = 'FakeUser'
        self.password = 'FakePassword'
        self.logged_in = False
        self.rights = ['read', 'edit', 'upload', 'reupload', 'delete']
        self.unhandled: list[str] = []
        self.requests = 0
        # A continuation bug in this fake would otherwise loop forever.
        self.request_limit = 20000
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    ############################## lifecycle ##############################

    def start(self) -> str:
        """Serve on a free port and return the address to clone from."""
        wiki = self
        server = ThreadingHTTPServer(('127.0.0.1', 0), _handler_for(wiki))
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()
        return self.url

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    @property
    def url(self) -> str:
        assert self._server is not None, 'the wiki is not running'
        host, port = self._server.server_address[:2]
        return f'http://{host}:{port}/wiki'

    ########################### contents, for tests #######################

    def reset(self) -> None:
        """Empty the wiki, as wiki_reset did by restoring a database dump."""
        self.pages.clear()
        self.next_pageid = 1
        self.next_revid = 1
        self.logged_in = False
        self.unhandled.clear()
        self.requests = 0

    def page(self, title: str) -> Page | None:
        title = normalise_title(title)
        return next((p for p in self.pages.values() if p.title == title), None)

    def titles(self) -> list[str]:
        return sorted(page.title for page in self.pages.values())

    def edit_page(
        self,
        title: str,
        text: str,
        append: bool = False,
        summary: str = '',
        category: str | None = None,
        user: str = 'FakeUser',
    ) -> int:
        """Create or edit a page, and return the new revision id."""
        title = normalise_title(title)
        page = self.page(title)
        if page is None:
            page = Page(pageid=self.next_pageid, title=title)
            self.pages[self.next_pageid] = page
            self.next_pageid += 1
        if append and page.revisions:
            text = page.text + text
        if category is not None:
            text = f'{text}\n [[Category:{category}]]'
        revid = self.next_revid
        self.next_revid += 1
        page.revisions.append(
            Revision(
                revid=revid,
                user=user,
                timestamp=f'2011-01-01T00:{revid // 60:02d}:{revid % 60:02d}Z',
                comment=summary,
                text=text,
            )
        )
        return revid

    def delete_page(self, title: str) -> None:
        page = self.page(title)
        assert page is not None, f'no page called {title}'
        del self.pages[page.pageid]

    def upload_file(self, name: str, content: bytes, comment: str = 'upload a file') -> None:
        """Add a media file, as Special:Upload would."""
        revid = self.edit_page(f'File:{name}', comment, summary=comment)
        page = self.page(f'File:{name}')
        assert page is not None
        page.upload = content
        del revid

    ################################## API ################################

    def api(self, params: dict[str, str]) -> dict:
        """Answer one api.php request."""
        with self._lock:
            self.requests += 1
            if self.requests > self.request_limit:
                return self._unhandled({'too-many-requests': str(self.requests)})
            return self._dispatch(params)

    def _dispatch(self, params: dict[str, str]) -> dict:
        action = params.get('action', 'query')
        if action == 'login':
            return self._login(params)
        if action == 'edit':
            return self._edit(params)
        if action == 'delete':
            return self._delete(params)
        if action == 'upload':
            return self._upload(params)
        if action == 'parse':
            return {
                'parse': {
                    'title': params.get('title', ''),
                    'text': {'*': f'<p>PARSED: {params.get("text", "")}</p>'},
                }
            }
        if action == 'query':
            return self._query(params)
        return self._unhandled(params)

    def _unhandled(self, params: dict[str, str]) -> dict:
        """Refuse rather than guess, and remember it so a test can assert on it."""
        self.unhandled.append(repr(sorted(params.items())))
        return {
            'error': {
                'code': 'unhandled-by-fake',
                'info': f'the fake wiki does not implement {sorted(params)}',
            }
        }

    def _userinfo(self) -> dict:
        return {
            'id': 1 if self.logged_in else 0,
            'name': self.username if self.logged_in else '127.0.0.1',
            'groups': ['*'],
            'rights': self.rights,
        }

    def _login(self, params: dict[str, str]) -> dict:
        name, password = params.get('lgname', ''), params.get('lgpassword', '')
        if name == self.username and password == self.password:
            self.logged_in = True
            return {'login': {'result': 'Success', 'lgusername': name}}
        return {'login': {'result': 'Failed', 'reason': 'Incorrect username or password'}}

    def _edit(self, params: dict[str, str]) -> dict:
        title, text = params.get('title', ''), params.get('text', '')
        revid = self.edit_page(title, text, summary=params.get('summary', ''), user='Pusher')
        return {'edit': {'result': 'Success', 'newrevid': revid, 'title': title}}

    def _delete(self, params: dict[str, str]) -> dict:
        title = params.get('title', '')
        if self.page(title) is None:
            return {'error': {'code': 'missingtitle', 'info': 'no such page'}}
        self.delete_page(title)
        return {'delete': {'title': title}}

    def _upload(self, params: dict[str, str]) -> dict:
        name = params.get('filename', '')
        self.upload_file(
            name,
            params.get('file', '').encode('utf-8', 'surrogateescape'),
            comment=params.get('comment', ''),
        )
        return {'upload': {'result': 'Success', 'filename': name}}

    def _query(self, params: dict[str, str]) -> dict:
        query: dict[str, Any] = {'userinfo': self._userinfo()}
        result: dict[str, Any] = {'query': query}
        meta, prop, listing = (params.get(k, '') for k in ('meta', 'prop', 'list'))

        if 'tokens' in meta:
            return {'query': {'tokens': {'csrftoken': 'faketoken+\\'}}}
        if 'siteinfo' in meta:
            siprop = params.get('siprop', '')
            if 'general' in siprop:
                query['general'] = {
                    'generator': 'MediaWiki 1.43.0',
                    'sitename': 'Fake Wiki',
                    'server': self.url,
                }
            if 'namespaces' in siprop:
                query['namespaces'] = {
                    str(number): (
                        {'id': number, '*': ''}
                        if number == 0
                        else {'id': number, 'canonical': name, '*': name}
                    )
                    for name, number in NAMESPACES.items()
                }
            if 'fileextensions' in siprop:
                query['fileextensions'] = [{'ext': ext} for ext in FILE_EXTENSIONS]
            return result

        if listing == 'allpages':
            return self._allpages(params, result)
        if listing == 'categorymembers':
            category = params.get('cmtitle', '').removeprefix('Category:')
            query['categorymembers'] = [
                {'pageid': page.pageid, 'ns': page.namespace, 'title': page.title}
                for page in sorted(self.pages.values(), key=lambda p: p.pageid)
                if f'Category:{category}' in page.links('Category')
                and (not params.get('cmnamespace') or page.namespace == int(params['cmnamespace']))
            ]
            return result
        if listing == 'recentchanges':
            return {'query': {'recentchanges': [{'revid': self.next_revid - 1}]}}

        if prop == 'revisions':
            return self._revisions(params, result)
        if prop in ('imageinfo', 'info|imageinfo'):
            return self._imageinfo(params, result)
        if prop == 'links|images':
            query['pages'] = {
                str(page.pageid): {
                    'pageid': page.pageid,
                    'ns': page.namespace,
                    'title': page.title,
                    'images': [{'title': t} for t in page.links('File')],
                }
                for page in self.pages.values()
                if page.title in params.get('titles', '').split('|')
            }
            return result
        if params.get('titles') and not prop:
            return self._titles(params, result)
        if meta and not prop and not listing:
            return result  # a bare meta=userinfo, which mwclient re-fetches
        return self._unhandled(params)

    def _allpages(self, params: dict[str, str], result: dict) -> dict:
        namespace = int(params.get('apnamespace', 0))
        pages = [
            p
            for p in sorted(self.pages.values(), key=lambda p: p.pageid)
            if p.namespace == namespace
        ]
        start = int(params.get('apcontinue', 0))
        limit = 500
        window = pages[start : start + limit]
        result['query']['allpages'] = [
            {'pageid': p.pageid, 'ns': p.namespace, 'title': p.title} for p in window
        ]
        if start + limit < len(pages):
            result['continue'] = {'apcontinue': str(start + limit), 'continue': '-||'}
        return result

    def _titles(self, params: dict[str, str], result: dict) -> dict:
        wanted = params.get('titles', '').split('|')
        pages, missing = {}, -1
        normalized = []
        for title in wanted:
            canonical = normalise_title(title)
            if canonical != title:
                normalized.append({'from': title, 'to': canonical})
            page = self.page(canonical) or self.page(title)
            if page is None:
                pages[str(missing)] = {'ns': 0, 'title': canonical, 'missing': ''}
                missing -= 1
            else:
                pages[str(page.pageid)] = {
                    'pageid': page.pageid,
                    'ns': page.namespace,
                    'title': page.title,
                }
        if normalized:
            result['query']['normalized'] = normalized
        result['query']['pages'] = pages
        return result

    def _revisions(self, params: dict[str, str], result: dict) -> dict:
        wanted_props = params.get('rvprop', '').split('|')
        pages: dict[str, dict] = {}

        def record(revision: Revision) -> dict:
            out: dict = {'revid': revision.revid}
            if 'timestamp' in wanted_props:
                out['timestamp'] = revision.timestamp
            if 'comment' in wanted_props:
                out['comment'] = revision.comment
            if 'user' in wanted_props:
                out['user'] = revision.user
            if 'content' in wanted_props and revision.text is not None:
                out['*'] = revision.text
            return out

        if params.get('pageids'):
            page = self.pages.get(int(params['pageids']))
            if page is None:
                return self._unhandled(params)
            # rvstartid begins the walk, rvcontinue resumes it.
            offset = int(params.get('rvcontinue') or params.get('rvstartid') or 0)
            revisions = [r for r in page.revisions if r.revid >= offset]
            limit = int(params.get('rvlimit', 500))
            window, rest = revisions[:limit], revisions[limit:]
            result['query']['pages'] = {
                str(page.pageid): {
                    'pageid': page.pageid,
                    'ns': page.namespace,
                    'title': page.title,
                    'revisions': [record(r) for r in window],
                }
            }
            if rest:
                result['continue'] = {'rvcontinue': str(rest[0].revid), 'continue': '-||'}
            return result

        if params.get('revids'):
            wanted = {int(r) for r in params['revids'].split('|')}
            for page in self.pages.values():
                found = [r for r in page.revisions if r.revid in wanted]
                if found:
                    pages[str(page.pageid)] = {
                        'pageid': page.pageid,
                        'ns': page.namespace,
                        'title': page.title,
                        'revisions': [record(r) for r in found],
                    }
            result['query']['pages'] = pages
            return result

        if params.get('titles'):
            page = self.page(params['titles'])
            if page is None:
                result['query']['pages'] = {
                    '-1': {'ns': 0, 'title': params['titles'], 'missing': ''}
                }
            else:
                result['query']['pages'] = {
                    str(page.pageid): {
                        'pageid': page.pageid,
                        'ns': page.namespace,
                        'title': page.title,
                        'revisions': [record(page.revisions[-1])],
                    }
                }
            return result

        return self._unhandled(params)

    def _imageinfo(self, params: dict[str, str], result: dict) -> dict:
        title = params.get('titles', '')
        page = self.page(title)
        if page is None:
            result['query']['pages'] = {
                '-1': {'ns': 6, 'title': title, 'missing': '', 'protection': []}
            }
            return result
        info: dict = {'timestamp': page.revisions[-1].timestamp}
        if 'url' in params.get('iiprop', ''):
            info['url'] = f'{self.url}/media/{title.removeprefix("File:")}'
        result['query']['pages'] = {
            str(page.pageid): {
                'pageid': page.pageid,
                'ns': page.namespace,
                'title': page.title,
                'protection': [],
                'imageinfo': [info],
            }
        }
        return result

    def media(self, name: str) -> bytes | None:
        page = self.page(f'File:{name}')
        return page.upload if page is not None else None


TEMPLATE = (
    '<!DOCTYPE html>\n<html><head><title>Fake Wiki</title>'
    '<link rel="stylesheet" href="/w/load.php"></head>'
    '<body><a href="/wiki/Main_Page">home</a>'
    '<div id="bodyContent"><p>server-rendered</p></div></body></html>'
)


def _parse_multipart(body: bytes, content_type: str) -> dict[str, str]:
    """Pull the fields out of a multipart upload."""
    boundary = content_type.split('boundary=')[1].strip('"').encode()
    fields = {}
    for part in body.split(b'--' + boundary):
        if b'\r\n\r\n' not in part:
            continue
        head, _, value = part.partition(b'\r\n\r\n')
        name = re.search(rb'name="([^"]+)"', head)
        if name:
            fields[name.group(1).decode()] = value.removesuffix(b'\r\n').decode(
                'utf-8', 'surrogateescape'
            )
    return fields


def _handler_for(wiki: FakeWiki) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass  # the tests are noisy enough

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if '/media/' in parsed.path:
                content = wiki.media(parsed.path.split('/media/', 1)[1])
                if content is None:
                    return self.send_error(404)
                return self._send(content, 'application/octet-stream')
            if parsed.path.endswith('/index.php'):
                return self._send(TEMPLATE.encode('utf-8'), 'text/html; charset=utf-8')
            return self._api(parse_qs(parsed.query))

        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            content_type = self.headers.get('Content-Type', '')
            if content_type.startswith('multipart/form-data'):
                return self._api(_parse_multipart(body, content_type), flat=True)
            return self._api(parse_qs(body.decode('utf-8')))

        def _api(self, params: dict, flat: bool = False) -> None:
            single = params if flat else {k: v[0] for k, v in params.items()}
            payload = json.dumps(wiki.api(single)).encode('utf-8')
            self._send(payload, 'application/json; charset=utf-8')

        def _send(self, payload: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return Handler
