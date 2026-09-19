"""Cloning a wiki, whole or in part.

Ported from t9360-mw-to-git-clone.sh.
"""

import unittest

from gitmwtest import GitMediaWikiTestCase

MAIN_PAGE = 'Main Page'


class CloneTest(GitMediaWikiTestCase):
    def subjects(self, *titles: str) -> list[str]:
        """The named pages plus the Main Page every wiki starts with."""
        return [MAIN_PAGE, *titles]

    def log(self, repository, *args: str) -> list[str]:
        """Commit subjects, newest first."""
        return self.git('log', '--format=%s', *args, cwd=repository).stdout.splitlines()

    def committers(self, repository, *args: str) -> list[str]:
        """Committer names, newest first."""
        return self.git('log', '--format=%cn', *args, cwd=repository).stdout.splitlines()

    def test_log_holds_the_edit_summary(self) -> None:
        self.wiki.edit_page('foo', 'this is not important', summary='this must be the same')

        repository = self.clone()

        self.assertEqual(['this must be the same'], self.log(repository, 'HEAD^..HEAD'))

    # The shell suite marked this test_expect_failure. It passes here, and I
    # could not establish why it did not there: it is not the revision
    # ordering (it still passes with that fix reverted) and it is not the
    # -s=VALUE option form (Getopt::Long accepted it). What is left is either
    # real-MediaWiki behaviour the fake does not reproduce, or the shell
    # test's own construction. Worth re-checking against a real wiki.
    def test_log_holds_every_edit_summary_of_each_page(self) -> None:
        self.wiki.edit_page('daddy', 'this is not important', summary='this must be the same')
        self.wiki.edit_page(
            'daddy', 'neither is this', append=True, summary='this must also be the same'
        )
        self.wiki.edit_page('daddy', 'neither is this', append=True, summary='same same same')
        self.wiki.edit_page('dj', 'dont care', summary='identical')
        self.wiki.edit_page('dj', 'dont care either', append=True, summary='identical too')

        repository = self.clone()

        self.assertEqual(
            ['same same same', 'this must also be the same', 'this must be the same'],
            self.log(repository, 'Daddy.mw'),
        )
        self.assertEqual(['identical too', 'identical'], self.log(repository, 'Dj.mw'))

    def test_the_wiki_user_becomes_the_committer(self) -> None:
        self.wiki.edit_page('foo', 'this is not important', user='Groyn88')

        repository = self.clone()

        self.assertEqual(['Groyn88'], self.committers(repository, 'HEAD^..HEAD'))

    def test_a_user_imported_from_another_wiki_still_makes_a_committer(self) -> None:
        # Such a user keeps the wiki they came from as a prefix, and the '>'
        # would otherwise close fast-import's ident before it opened.
        self.wiki.edit_page('foo', 'this is not important', user='en>Groyn88')

        repository = self.clone()

        self.assertEqual(['en_Groyn88'], self.committers(repository, 'HEAD^..HEAD'))

    def test_a_fresh_wiki_gives_only_the_main_page(self) -> None:
        repository = self.clone()

        self.assertEqual(['Main_Page.mw'], self.page_files(repository))

    def test_a_deleted_page_is_not_fetched(self) -> None:
        self.wiki.edit_page('foo', 'this page must be deleted before the clone')
        self.wiki.delete_page('foo')

        repository = self.clone()

        self.assertEqual(['Main_Page.mw'], self.page_files(repository))

    def test_added_pages_are_cloned(self) -> None:
        self.wiki.edit_page('foo', ' I will be cloned')
        self.wiki.edit_page('bar', 'I will be cloned')

        repository = self.clone()

        self.assertRepositoryMatchesWiki(repository)

    # The shell suite marked this test_expect_failure. It passes here, and I
    # could not establish why it did not there: it is not the revision
    # ordering (it still passes with that fix reverted) and it is not the
    # -s=VALUE option form (Getopt::Long accepted it). What is left is either
    # real-MediaWiki behaviour the fake does not reproduce, or the shell
    # test's own construction. Worth re-checking against a real wiki.
    def test_an_edited_page_keeps_both_summaries(self) -> None:
        self.wiki.edit_page('foo', 'this page will be edited', summary='first edition of page foo')
        self.wiki.edit_page(
            'foo', 'this page has been edited and must be on the clone ', append=True
        )

        repository = self.clone()

        self.assertRepositoryMatchesWiki(repository)
        self.assertEqual(['first edition of page foo'], self.log(repository, 'HEAD^', 'Foo.mw'))

    def test_pages_deleted_before_the_clone_are_absent(self) -> None:
        self.wiki.edit_page('foo', 'this page will not be deleted')
        self.wiki.edit_page('bar', 'I must not be erased')
        self.wiki.edit_page('namnam', 'I will not be there at the end')
        self.wiki.edit_page('nyancat', 'nyan nyan nyan delete me')
        self.wiki.delete_page('namnam')
        self.wiki.delete_page('nyancat')

        repository = self.clone()

        self.assertRepositoryMatchesWiki(repository)
        self.assertNotIn('Namnam.mw', self.page_files(repository))
        self.assertNotIn('Nyancat.mw', self.page_files(repository))

    # The shell suite marked this test_expect_failure. It passes here, and I
    # could not establish why it did not there: it is not the revision
    # ordering (it still passes with that fix reverted) and it is not the
    # -s=VALUE option form (Getopt::Long accepted it). What is left is either
    # real-MediaWiki behaviour the fake does not reproduce, or the shell
    # test's own construction. Worth re-checking against a real wiki.
    def test_cloning_one_named_page(self) -> None:
        self.wiki.edit_page('foo', 'I will not be cloned')
        self.wiki.edit_page('bar', 'Do not clone me')
        self.wiki.edit_page('namnam', 'I will be cloned :)', summary='this log must stay')
        self.wiki.edit_page('nyancat', 'nyan nyan nyan you cant clone me')

        repository = self.clone(pages='namnam')

        self.assertEqual(['Namnam.mw'], self.page_files(repository))
        self.assertEqual(['this log must stay'], self.log(repository))
        self.assertPageMatches(repository, 'Namnam')

    def test_cloning_several_named_pages(self) -> None:
        self.wiki.edit_page('foo', 'I will be there')
        self.wiki.edit_page('bar', 'I will not disappear')
        self.wiki.edit_page('namnam', 'I be erased')
        self.wiki.edit_page('nyancat', 'nyan nyan nyan you will not erase me')
        self.wiki.delete_page('namnam')

        repository = self.clone(pages='foo bar nyancat namnam')

        self.assertRepositoryMatchesWiki(repository, ['Foo', 'Bar', 'Nyancat'])

    def test_cloning_named_pages_leaves_the_rest_behind(self) -> None:
        for title in ('foo', 'bar', 'dummy', 'cloned_1', 'cloned_2', 'cloned_3'):
            self.wiki.edit_page(title, f'{title} contents')

        repository = self.clone(pages='cloned_1 cloned_2 cloned_3')

        self.assertRepositoryMatchesWiki(repository, ['Cloned 1', 'Cloned 2', 'Cloned 3'])

    def test_shallow_fetches_one_revision_per_page(self) -> None:
        self.wiki.edit_page('foo', '1st revision, should be cloned')
        self.wiki.edit_page('bar', '1st revision, should be cloned')
        self.wiki.edit_page('nyan', '1st revision, should not be cloned')
        self.wiki.edit_page('nyan', '2nd revision, should be cloned')

        repository = self.clone(shallow='true')

        self.assertRepositoryMatchesWiki(repository, self.subjects('Foo', 'Bar', 'Nyan'))
        for name in ('Nyan.mw', 'Foo.mw', 'Bar.mw', 'Main_Page.mw'):
            self.assertEqual(1, len(self.log(repository, name)), f'revisions of {name}')

    def test_shallow_skips_a_deleted_page(self) -> None:
        self.wiki.edit_page('foo', '1st revision, will be deleted')
        self.wiki.edit_page('bar', '1st revision, should be cloned')
        self.wiki.edit_page('nyan', '1st revision, should not be cloned')
        self.wiki.edit_page('nyan', '2nd revision, should be cloned')
        self.wiki.delete_page('foo')

        repository = self.clone(shallow='true')

        self.assertRepositoryMatchesWiki(repository, self.subjects('Bar', 'Nyan'))
        for name in ('Nyan.mw', 'Bar.mw', 'Main_Page.mw'):
            self.assertEqual(1, len(self.log(repository, name)), f'revisions of {name}')

    def test_cloning_a_category(self) -> None:
        self.wiki.edit_page('Foo', 'I will be cloned', category='Category')
        self.wiki.edit_page('Bar', 'Meet me on the repository', category='Category')
        self.wiki.edit_page('Dummy', 'I will not come')
        self.wiki.edit_page('BarWrong', 'I will stay online only', category='NotCategory')

        repository = self.clone(categories='Category')

        self.assertRepositoryMatchesWiki(repository, ['Foo', 'Bar'])

    def test_cloning_a_category_that_changed_before_the_clone(self) -> None:
        self.wiki.edit_page('Tobedeleted', 'this page will be deleted', category='Catone')
        self.wiki.edit_page('Tobeedited', 'this page will be modified', category='Catone')
        self.wiki.edit_page('Normalone', 'this page wont be modified', category='Catone')
        self.wiki.edit_page('Notconsidered', 'this page will not appear on local')
        self.wiki.edit_page(
            'Othercategory', 'this page will not appear on local', category='Cattwo'
        )
        self.wiki.edit_page('Tobeedited', 'this page have been modified', append=True)
        self.wiki.delete_page('Tobedeleted')

        repository = self.clone(categories='Catone')

        self.assertRepositoryMatchesWiki(repository, ['Tobeedited', 'Normalone'])


if __name__ == '__main__':
    unittest.main()
