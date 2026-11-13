"""git clone-mediawiki: cloning a page or a category from its address."""

import unittest
from urllib.parse import urlsplit

from gitmwtest import GitMediaWikiTestCase


class CloneMediaWikiTest(GitMediaWikiTestCase):
    def page_url(self, path: str) -> str:
        """The address the browser shows for ``path`` on the fake wiki."""
        parts = urlsplit(self.wiki.url)
        return f'{parts.scheme}://{parts.netloc}{path}'

    def config(self, repository, name: str) -> str:
        return self.git('config', name, cwd=repository).stdout.strip()

    def test_clones_an_article(self) -> None:
        self.wiki.edit_page('Innsbruck', 'Hauptstadt Tirols')
        self.wiki.edit_page('Wien', 'not wanted')

        self.git('clone-mediawiki', self.page_url('/view/Innsbruck'))

        repository = self.workdir / 'Innsbruck'
        self.assertEqual(['Innsbruck.mw'], self.page_files(repository))
        self.assertEqual('Innsbruck', self.config(repository, 'remote.origin.pages'))
        self.assertEqual(
            f'mediawiki::{self.wiki.url}', self.config(repository, 'remote.origin.url')
        )
        self.assertNothingUnhandled()

    def test_clones_a_category(self) -> None:
        self.wiki.edit_page('V8', 'engine [[Category:JavaScript engines]]')
        self.wiki.edit_page('SpiderMonkey', 'engine [[Category:JavaScript engines]]')
        self.wiki.edit_page('Wien', 'not wanted')

        self.git('clone-mediawiki', self.page_url('/view/Category:JavaScript_engines'))

        repository = self.workdir / 'JavaScript_engines'
        self.assertEqual(['SpiderMonkey.mw', 'V8.mw'], self.page_files(repository))
        self.assertEqual(
            'Category:JavaScript_engines', self.config(repository, 'remote.origin.categories')
        )
        self.assertNothingUnhandled()

    def test_category_depth_expands_subcategories(self) -> None:
        self.wiki.edit_page('V8', 'engine [[Category:JavaScript engines]]')
        self.wiki.edit_page('Category:Free engines', 'subcategory [[Category:JavaScript engines]]')
        self.wiki.edit_page('SpiderMonkey', 'engine [[Category:Free engines]]')
        self.wiki.edit_page('Category:Mozilla', 'deeper [[Category:Free engines]]')
        self.wiki.edit_page('Rhino', 'too deep [[Category:Mozilla]]')

        shallow = self.git(
            'clone-mediawiki', '--dry-run', self.page_url('/view/Category:JavaScript_engines')
        )
        self.assertIn('remote.origin.categories=Category:JavaScript_engines ', shallow.stdout)

        self.git(
            'clone-mediawiki',
            '--category-depth',
            '2',
            self.page_url('/view/Category:JavaScript_engines'),
        )

        # The subcategories' own pages are members too; Rhino is a level deeper.
        repository = self.workdir / 'JavaScript_engines'
        self.assertEqual(
            ['Category:Free_engines.mw', 'Category:Mozilla.mw', 'SpiderMonkey.mw', 'V8.mw'],
            self.page_files(repository),
        )
        self.assertEqual(
            'Category:JavaScript_engines Category:Free_engines',
            self.config(repository, 'remote.origin.categories'),
        )
        self.assertNothingUnhandled()

    def test_depth_limits_the_history(self) -> None:
        self.wiki.edit_page('Innsbruck', 'first')
        self.wiki.edit_page('Innsbruck', 'second')
        self.wiki.edit_page('Innsbruck', 'third')

        self.git('clone-mediawiki', '--depth', '1', self.page_url('/view/Innsbruck'))

        repository = self.workdir / 'Innsbruck'
        self.assertEqual('1', self.config(repository, 'remote.origin.depth'))
        log = self.git('log', '--format=%H', 'Innsbruck.mw', cwd=repository).stdout
        self.assertEqual(1, len(log.splitlines()))
        self.assertNothingUnhandled()

    def test_refuses_a_depth_of_zero(self) -> None:
        completed = self.git(
            'clone-mediawiki', '--depth', '0', self.page_url('/view/Innsbruck'), check=False
        )

        self.assertNotEqual(0, completed.returncode)
        self.assertIn('0 is not a positive number', completed.stderr)

    def test_takes_the_title_from_index_php(self) -> None:
        self.wiki.edit_page('Some page', 'content')

        completed = self.git(
            'clone-mediawiki',
            '--dry-run',
            self.page_url('/wiki/index.php?title=Some_page&action=history'),
            'here',
        )

        self.assertEqual(
            f'git clone -c remote.origin.pages=Some_page mediawiki::{self.wiki.url} here\n',
            completed.stdout,
        )
        self.assertFalse((self.workdir / 'here').exists())

    def test_refuses_a_missing_page(self) -> None:
        completed = self.git('clone-mediawiki', self.page_url('/view/Nowhere'), check=False)

        self.assertNotEqual(0, completed.returncode)
        self.assertIn('There is no page "Nowhere"', completed.stderr)


if __name__ == '__main__':
    unittest.main()
