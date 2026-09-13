"""Pushing and pulling, run under each fetch strategy.

Ported from push-pull-tests.sh, which t9361 and t9364 both sourced: t9361 with
the default fetch strategy and t9364 with by_rev.
"""

import re
import unittest

from gitmwtest import GitMediaWikiTestCase


class PushPullTest(GitMediaWikiTestCase):
    """The cases, with whatever fetch strategy the helper picks by default."""

    def test_push_when_revisions_of_pages_interleave(self) -> None:
        # Interleave the revision ids across two pages, so that the newest
        # revision on the wiki does not belong to whichever page the API
        # returns last. The note on the last imported commit is what gates the
        # next push, so it has to be that newest revision.
        self.wiki.edit_page('Foo', 'first')
        self.wiki.edit_page('Bar', 'second')
        self.wiki.edit_page('Foo', 'third')

        repository = self.clone()
        self.commit(repository, 'a local change', **{'Foo.mw': 'a local change\n'})
        self.git('push', cwd=repository)

        self.assertEqual('a local change', self.wiki_page('Foo').text.strip())

    def test_pull_after_adding_a_wiki_page(self) -> None:
        repository = self.clone()
        self.wiki.edit_page('Foo', 'page created after the git clone')

        self.git('pull', cwd=repository)

        self.assertRepositoryMatchesWiki(repository)

    def test_pull_after_editing_a_wiki_page(self) -> None:
        self.wiki.edit_page('Foo', 'page created before the git clone')
        repository = self.clone()
        self.wiki.edit_page('Foo', '\nnew line added on the wiki', append=True)

        self.git('pull', cwd=repository)

        self.assertRepositoryMatchesWiki(repository)

    def test_pull_merges_a_change_that_does_not_conflict(self) -> None:
        self.wiki.edit_page('Foo', '1 init\n3\n5\n')
        repository = self.clone()
        self.wiki.edit_page('Foo', '1 init\n2 added on the wiki after the clone\n3\n5\n')

        self.commit(
            repository,
            'conflicting change on foo',
            **{'Foo.mw': '1 init\n3\n4 added in git after the clone\n5\n'},
        )
        self.git('pull', cwd=repository)
        self.git('push', cwd=repository)

        merged = (repository / 'Foo.mw').read_text(encoding='utf-8')
        self.assertIn('2 added on the wiki after the clone', merged)
        self.assertIn('4 added in git after the clone', merged)

    def test_push_after_adding_a_page(self) -> None:
        repository = self.clone()
        self.assertFalse((repository / 'Foo.mw').exists())

        self.commit(repository, 'Foo', **{'Foo.mw': 'hello world\n'})
        self.git('push', cwd=repository)

        self.assertRepositoryMatchesWiki(repository)

    def test_push_after_editing_a_page(self) -> None:
        self.wiki.edit_page('Foo', 'page created before the git clone')
        repository = self.clone()

        content = (repository / 'Foo.mw').read_text(encoding='utf-8')
        self.commit(
            repository,
            'edit file Foo.mw',
            **{'Foo.mw': content + 'new line added in the file Foo.mw\n'},
        )
        self.git('push', cwd=repository)

        self.assertRepositoryMatchesWiki(repository)

    @unittest.expectedFailure
    def test_push_after_deleting_a_page(self) -> None:
        # Deleting a page usually needs privileges, so the bridge replaces its
        # content with [[Category:Deleted]] instead. The page stays.
        self.wiki.edit_page('Foo', 'wiki page added before git clone')
        repository = self.clone()

        self.git('rm', 'Foo.mw', cwd=repository)
        self.git('commit', '-am', 'page Foo.mw deleted', cwd=repository)
        self.git('push', cwd=repository)

        self.assertIsNone(self.wiki.page('Foo'))

    def test_pull_conflicts_and_the_conflict_can_be_resolved(self) -> None:
        repository = self.clone()
        self.wiki.edit_page('Foo', '1 conflict\n3 wiki\n4\n')

        self.commit(repository, 'conflict created', **{'Foo.mw': '1 conflict\n2 git\n4\n'})
        self.assertNotEqual(0, self.git('pull', cwd=repository, check=False).returncode)

        conflicted = (repository / 'Foo.mw').read_text(encoding='utf-8')
        self.assertIn('<<<<<<<', conflicted)
        (repository / 'Foo.mw').write_text(re.sub(r'[<=>].*', '', conflicted), encoding='utf-8')
        self.git('commit', '-am', 'merge conflict solved', cwd=repository)
        self.git('push', cwd=repository)

    @unittest.expectedFailure
    def test_pull_after_deleting_a_wiki_page(self) -> None:
        # Deletions on the wiki are not revisions, so an import never sees them.
        self.wiki.edit_page('Foo', 'wiki page added before the git clone')
        repository = self.clone()

        self.wiki.delete_page('Foo')
        self.git('pull', cwd=repository)

        self.assertFalse((repository / 'Foo.mw').exists())


class PushPullByRevTest(PushPullTest):
    """All of the above again, fetching by revision. This was t9364."""

    fetch_strategy = 'by_rev'


if __name__ == '__main__':
    unittest.main()
