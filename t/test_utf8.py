"""Page names that are awkward: accents, spaces, and characters that mean
something to the wiki, to a file system, or to the fast-import stream.

Ported from t9362-mw-to-git-utf8.sh.
"""

import unittest

from gitmwtest import GitMediaWikiTestCase


class SpecialCharactersTest(GitMediaWikiTestCase):
    def test_clone_with_accents_in_page_names(self) -> None:
        for title in ('féé', 'kèè', 'hàà', 'kîî', 'foo'):
            self.wiki.edit_page(title, 'This page must be délétéd before clone')

        self.assertRepositoryMatchesWiki(self.clone())

    def test_pull_with_accents_in_page_names(self) -> None:
        self.wiki.edit_page('kîî', 'this page must be cloned')
        self.wiki.edit_page('foo', 'this page must be cloned')
        repository = self.clone()
        self.wiki.edit_page('éàîôû', 'This page must be pulled')

        self.git('pull', cwd=repository)

        self.assertRepositoryMatchesWiki(repository)

    def test_cloning_a_chosen_page_with_accents(self) -> None:
        self.wiki.edit_page('kîî', 'this page must be cloned')

        repository = self.clone(pages='kîî')

        self.assertRepositoryMatchesWiki(repository, ['Kîî'])

    def test_shallow_with_accents(self) -> None:
        self.wiki.edit_page('néoà', '1st revision, should not be cloned')
        self.wiki.edit_page('néoà', '2nd revision, should be cloned')

        repository = self.clone(shallow='true')

        self.assertRepositoryMatchesWiki(repository, ['Main Page', 'Néoà'])
        for name in ('Néoà.mw', 'Main_Page.mw'):
            self.assertEqual(
                1, len(self.git('log', '--oneline', name, cwd=repository).stdout.splitlines())
            )

    def test_cloning_a_page_whose_first_letter_has_an_accent(self) -> None:
        self.wiki.edit_page('îî', 'this page must be cloned')

        repository = self.clone(pages='îî')

        # MediaWiki capitalises the first letter, accent and all.
        self.assertRepositoryMatchesWiki(repository, ['Îî'])

    def test_push_with_accents(self) -> None:
        self.wiki.edit_page('féé', 'lots of accents : éèàÖ')
        self.wiki.edit_page('foo', 'this page must be cloned')
        repository = self.clone()

        self.commit(repository, 'A new page appears', **{'Pîkächû.mw': 'A wild Pîkächû appears\n'})
        self.git('push', cwd=repository)

        self.assertRepositoryMatchesWiki(repository)

    def test_clone_with_accents_and_spaces(self) -> None:
        self.wiki.edit_page('é à î', 'this page must be délété before the clone')

        self.assertRepositoryMatchesWiki(self.clone())

    def test_dollar_in_a_page_name_from_the_wiki(self) -> None:
        self.wiki.edit_page('file_$_foo', 'expect to be called file_$_foo')

        repository = self.clone()

        self.assertIn('File_$_foo.mw', self.page_files(repository))
        self.assertRepositoryMatchesWiki(repository)

    def test_dollar_in_a_file_name_pushed_to_the_wiki(self) -> None:
        repository = self.clone()

        self.commit(
            repository, 'file File_$_foo.mw', **{'File_$_foo.mw': 'this file is called it\n'}
        )
        self.git('push', cwd=repository)

        self.assertRepositoryMatchesWiki(repository)

    @unittest.expectedFailure
    def test_two_files_differing_only_in_their_first_letter(self) -> None:
        # MediaWiki capitalises the first letter, so foo.mw and Foo.mw are the
        # same page and one of them loses.
        repository = self.clone()

        self.commit(
            repository,
            'file foo.mw',
            **{'foo.mw': 'my new file foo\n', 'Foo.mw': 'my new file Foo\n'},
        )
        self.git('push', cwd=repository)

        self.assertRepositoryMatchesWiki(repository)

    @unittest.expectedFailure
    def test_a_page_whose_name_begins_with_a_forbidden_character(self) -> None:
        # MediaWiki will not have a title holding { or [, which is the whole
        # reason the bridge encodes them.
        self.wiki.edit_page('{char_1', 'expect to be renamed {char_1')
        self.wiki.edit_page('[char_2', 'expect to be renamed [char_2')

        repository = self.clone()

        self.assertIn('{char_1.mw', self.page_files(repository))

    def test_pull_a_title_whose_colon_is_not_a_namespace(self) -> None:
        self.wiki.edit_page('Foo:Bar', 'content')

        repository = self.clone()

        self.assertIn('Foo:Bar.mw', self.page_files(repository))

    def test_push_a_title_whose_colon_is_not_a_namespace(self) -> None:
        repository = self.clone()

        self.commit(repository, 'add page with colon', **{'NotANameSpace:Page.mw': 'content\n'})
        self.git('push', cwd=repository)

        self.assertIsNotNone(self.wiki.page('NotANameSpace:Page'))

    def test_encoded_characters_are_decoded_from_the_wiki(self) -> None:
        self.wiki.edit_page('char_%_7b_1', 'expect to be renamed char{_1')
        self.wiki.edit_page('char_%_5b_2', 'expect to be renamed char[_2')

        repository = self.clone()

        self.assertIn('Char{_1.mw', self.page_files(repository))
        self.assertIn('Char[_2.mw', self.page_files(repository))

    @unittest.expectedFailure
    def test_a_file_name_beginning_with_a_special_character(self) -> None:
        # Pushed, the leading { becomes _%_7b, so the page does not come back
        # under the name the file had.
        repository = self.clone()

        self.commit(
            repository,
            'committing some exotic file name...',
            **{'{char_1.mw': 'my new file {char_1\n', '[char_2.mw': 'my new file [char_2\n'},
        )
        self.git('push', cwd=repository)

        self.assertIsNotNone(self.wiki.page('{char_1'))

    def test_special_characters_are_encoded_towards_the_wiki(self) -> None:
        repository = self.clone()

        self.commit(
            repository,
            'committing some exotic file name...',
            **{'Char{_1.mw': 'my new file char{_1\n', 'Char[_2.mw': 'my new file char[_2\n'},
        )
        self.git('push', cwd=repository)

        self.assertIsNotNone(self.wiki.page('Char % 7b 1'))
        self.assertIsNotNone(self.wiki.page('Char % 5b 2'))

    def test_clone_a_page_name_holding_slashes(self) -> None:
        self.wiki.edit_page('/fo/o', 'this is not important')

        repository = self.clone()

        self.assertIn('%2Ffo%2Fo.mw', self.page_files(repository))
        self.assertPageMatches(repository, '/fo/o')

    def test_push_a_file_name_holding_the_slash_escape(self) -> None:
        repository = self.clone()

        self.commit(repository, '%2Ffo%2Fo added', **{'%2Ffo%2Fo.mw': 'I will be on the wiki\n'})
        self.git('push', cwd=repository)

        self.assertIsNotNone(self.wiki.page('/fo/o'))
        self.assertPageMatches(repository, '/fo/o')

    def test_clone_a_page_name_holding_backslashes(self) -> None:
        self.wiki.edit_page('\\ko\\o', 'this is not important')

        repository = self.clone()

        self.assertIn('\\ko\\o.mw', self.page_files(repository))
        self.assertPageMatches(repository, '\\ko\\o')

    def test_push_a_file_name_holding_backslashes(self) -> None:
        repository = self.clone()

        self.commit(repository, '\\ko\\o added', **{'\\ko\\o.mw': 'I will be on the wiki\n'})
        self.git('push', cwd=repository)

        self.assertIsNotNone(self.wiki.page('\\ko\\o'))
        self.assertPageMatches(repository, '\\ko\\o')

    def test_clone_a_page_name_holding_a_backslash_escape(self) -> None:
        self.wiki.edit_page('\\no\\o', 'this is not important')

        repository = self.clone()

        self.assertIn('\\no\\o.mw', self.page_files(repository))
        self.assertPageMatches(repository, '\\no\\o')

    def test_push_a_file_name_holding_a_backslash_escape(self) -> None:
        repository = self.clone()

        self.commit(repository, '\\fo\\o added', **{'\\fo\\o.mw': 'I will be on the wiki\n'})
        self.git('push', cwd=repository)

        self.assertIsNotNone(self.wiki.page('\\fo\\o'))
        self.assertPageMatches(repository, '\\fo\\o')

    def test_fast_import_metacharacters_from_the_wiki(self) -> None:
        # A quote and a backslash both have to be escaped in the stream.
        self.wiki.edit_page('"file"_\\_foo', 'expect to be called "file"_\\_foo')

        repository = self.clone()

        self.assertIn('"file"_\\_foo.mw', self.page_files(repository))
        self.assertRepositoryMatchesWiki(repository)

    def test_fast_import_metacharacters_towards_the_wiki(self) -> None:
        repository = self.clone()

        self.commit(
            repository,
            'file "file"_\\_foo',
            **{'"file"_\\_foo.mw': 'this file is called "file"_\\_foo.mw\n'},
        )
        self.git('push', cwd=repository)

        self.assertRepositoryMatchesWiki(repository)


if __name__ == '__main__':
    unittest.main()
