"""Base class for the git-remote-mediawiki tests.

Each test gets an empty wiki and an empty directory, and drives the real
``git`` binary against the real helper scripts: nothing here imports the code
under test, so the remote-helper protocol, the PATH lookup and fast-import are
all exercised for real.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from fakewiki import FakeWiki, Page

REPO_ROOT = Path(__file__).resolve().parent.parent


class GitMediaWikiTestCase(unittest.TestCase):
    """A wiki, a scratch directory, and helpers for driving git at them."""

    wiki: FakeWiki
    _home: str

    #: Set by a subclass to clone with remote.origin.fetchStrategy.
    fetch_strategy: str | None = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.wiki = FakeWiki()
        cls.wiki.start()
        # Somewhere for `git config --global` to go that is not the real one.
        cls._home = tempfile.mkdtemp(prefix='git-mw-home.')

    @classmethod
    def tearDownClass(cls) -> None:
        cls.wiki.stop()
        shutil.rmtree(cls._home, ignore_errors=True)

    def setUp(self) -> None:
        self.wiki.reset()
        self.workdir = Path(tempfile.mkdtemp(prefix='git-mw-test.'))
        self.addCleanup(shutil.rmtree, self.workdir, ignore_errors=True)

    @property
    def remote(self) -> str:
        """The URL to clone from."""
        return f'mediawiki::{self.wiki.url}'

    def environment(self) -> dict[str, str]:
        """A git environment that is isolated and reproducible."""
        return os.environ | {
            'PATH': f'{REPO_ROOT}{os.pathsep}{os.environ["PATH"]}',
            'HOME': self._home,
            'GIT_CONFIG_GLOBAL': str(Path(self._home) / 'gitconfig'),
            'GIT_CONFIG_SYSTEM': os.devnull,
            'GIT_AUTHOR_NAME': 'Test',
            'GIT_AUTHOR_EMAIL': 'test@example.com',
            'GIT_COMMITTER_NAME': 'Test',
            'GIT_COMMITTER_EMAIL': 'test@example.com',
            'GIT_AUTHOR_DATE': '2020-01-01T00:00:00Z',
            'GIT_COMMITTER_DATE': '2020-01-01T00:00:00Z',
            # These tests predate git refusing to pull without being told how
            # to reconcile; they mean a merge.
            'GIT_CONFIG_COUNT': '1',
            'GIT_CONFIG_KEY_0': 'pull.rebase',
            'GIT_CONFIG_VALUE_0': 'false',
        }

    def git(
        self, *args: str, cwd: Path | None = None, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        """Run git, by default asserting that it succeeded."""
        completed = subprocess.run(
            ['git', *args],
            cwd=cwd or self.workdir,
            env=self.environment(),
            capture_output=True,
            text=True,
            check=False,
        )
        if check and completed.returncode != 0:
            self.fail(
                f'git {" ".join(args)} exited {completed.returncode}\n'
                f'--- stdout ---\n{completed.stdout}\n'
                f'--- stderr ---\n{completed.stderr}'
            )
        return completed

    def clone(self, directory: str = 'repo', **config: str) -> Path:
        """Clone the wiki, passing any keywords as remote.origin.<name>."""
        if self.fetch_strategy:
            config.setdefault('fetchStrategy', self.fetch_strategy)
        options = [
            argument
            for name, value in config.items()
            for argument in ('-c', f'remote.origin.{name}={value}')
        ]
        self.git('clone', *options, self.remote, directory)
        return self.workdir / directory

    def commit(self, repository: Path, message: str, **files: str) -> None:
        """Write files into the repository and commit them."""
        for name, content in files.items():
            (repository / name).write_text(content, encoding='utf-8')
        self.git('add', '-A', cwd=repository)
        self.git('commit', '-m', message, cwd=repository)

    def page_files(self, repository: Path) -> list[str]:
        """The tracked files, which is what the wiki's pages became."""
        listed = self.git('ls-files', cwd=repository).stdout.split()
        return sorted(listed)

    def wiki_page(self, title: str) -> Page:
        """The named page, failing the test if the wiki has no such page."""
        page = self.wiki.page(title)
        if page is None:
            self.fail(f'the wiki has no page called {title}; it has {self.wiki.titles()}')
        return page

    @staticmethod
    def page_file(title: str) -> str:
        """The file a page becomes.

        Spelled out from the documented rule rather than by calling the code
        under test, so that the test checks the rule instead of agreeing with
        whatever the implementation currently does.
        """
        return title.replace('/', '%2F').replace(' ', '_') + '.mw'

    def assertRepositoryMatchesWiki(self, repository: Path) -> None:
        """Every page of the wiki is in the repository with the same content.

        Whitespace runs are collapsed, as the shell tests\' diff -b did: the
        bridge adds and removes trailing newlines of its own accord.
        """

        def normalise(text: str) -> list[str]:
            return [' '.join(line.split()) for line in text.strip().splitlines()]

        expected = {self.page_file(page.title) for page in self.wiki.pages.values()}
        self.assertEqual(sorted(expected), self.page_files(repository))
        for page in self.wiki.pages.values():
            written = (repository / self.page_file(page.title)).read_text(encoding='utf-8')
            self.assertEqual(normalise(page.text), normalise(written), f'contents of {page.title}')

    def assertNothingUnhandled(self) -> None:
        """Fail if the helper asked the fake wiki something it does not implement."""
        self.assertEqual(
            [], self.wiki.unhandled, 'the helper asked the fake wiki something it does not fake'
        )
