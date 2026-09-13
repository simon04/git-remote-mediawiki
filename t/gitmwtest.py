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

from fakewiki import FakeWiki

REPO_ROOT = Path(__file__).resolve().parent.parent


class GitMediaWikiTestCase(unittest.TestCase):
    """A wiki, a scratch directory, and helpers for driving git at them."""

    wiki: FakeWiki
    _home: str

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

    def assertNothingUnhandled(self) -> None:
        """Fail if the helper asked the fake wiki something it does not implement."""
        self.assertEqual(
            [], self.wiki.unhandled, 'the helper asked the fake wiki something it does not fake'
        )
