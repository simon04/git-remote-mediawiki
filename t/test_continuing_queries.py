"""Queries whose results run past the API's 500-item limit.

Ported from t9365-continuing-queries.sh.
"""

import unittest

from gitmwtest import GitMediaWikiTestCase


class ContinuingQueriesTest(GitMediaWikiTestCase):
    def test_clones_a_page_with_more_than_500_revisions(self) -> None:
        for number in range(1, 502):
            self.wiki.edit_page('foo', f'revision {number}<br/>', append=True)
        self.assertEqual(501, len(self.wiki_page('foo').revisions))

        repository = self.clone()

        # Plus the Main Page every fresh MediaWiki starts with.
        self.assertEqual(['Foo.mw', 'Main_Page.mw'], self.page_files(repository))
        self.assertEqual(502, int(self.git('rev-list', '--count', 'HEAD', cwd=repository).stdout))
        self.assertNothingUnhandled()

    def test_clones_a_wiki_with_more_than_500_pages(self) -> None:
        for number in range(1, 502):
            self.wiki.edit_page(f'page {number}', f'contents of page {number}')

        repository = self.clone()

        self.assertEqual(502, len(self.page_files(repository)))  # plus the Main Page
        self.assertNothingUnhandled()


if __name__ == '__main__':
    unittest.main()
