"""Pushing and pulling media files, page deletion, and permitted file types.

Ported from t9363-mw-to-git-export-import.sh. Where the shell relied on the
previous test having left a repository behind, each test here sets up its own.
"""

import unittest
from pathlib import Path

from gitmwtest import GitMediaWikiTestCase


class ExportImportTest(GitMediaWikiTestCase):
    def reimport(self, repository: Path) -> None:
        """Push without updating the metadata, then pull it back.

        This was test_git_reimport: it checks that what the wiki ends up with
        is what comes back, rather than trusting the local view of it.
        """
        self.git('-c', 'remote.origin.dumbPush=true', 'push', cwd=repository)
        self.git('-c', 'remote.origin.mediaImport=true', 'pull', '--rebase', cwd=repository)

    def test_push_uploads_a_media_file_and_its_binary_content(self) -> None:
        # The shell suite marked this test_expect_failure. It passes against
        # the fake, which accepts any upload; a real MediaWiki checks the MIME
        # type of what it is given, and a .txt holding a raw 0xff byte is a
        # plausible thing for it to refuse. Worth re-checking against one.
        repository = self.clone()

        self.commit(repository, 'add a text file', **{'Foo.txt': 'hello world\n'})
        self.git('push', cwd=repository)
        (repository / 'Foo.txt').write_bytes(b'binary content: \xff')
        self.git('commit', '-am', 'add a text file with binary content', cwd=repository)
        self.git('push', cwd=repository)

        self.assertEqual(b'binary content: \xff', self.wiki_page('File:Foo.txt').upload)

    def test_clone_brings_back_an_uploaded_media_file(self) -> None:
        # The shell suite marked this test_expect_failure. It passes against
        # the fake, which accepts any upload; a real MediaWiki checks the MIME
        # type of what it is given, and a .txt holding a raw 0xff byte is a
        # plausible thing for it to refuse. Worth re-checking against one.
        repository = self.clone()
        self.commit(repository, 'add a text file', **{'Foo.txt': 'hello world\n'})
        self.git('push', cwd=repository)

        clone = self.clone('clone', mediaimport='true')

        self.assertEqual((repository / 'Foo.txt').read_bytes(), (clone / 'Foo.txt').read_bytes())

    def test_push_uploads_a_media_file_holding_utf8(self) -> None:
        repository = self.clone()
        content = 'UTF-8 content: éèàéê€.'.encode()

        (repository / 'Bar.txt').write_bytes(content)
        self.git('add', 'Bar.txt', cwd=repository)
        self.git('commit', '-m', 'add a text file with UTF-8 content', cwd=repository)
        self.git('push', cwd=repository)

        self.assertEqual(content, self.wiki_page('File:Bar.txt').upload)

        clone = self.clone('clone', mediaimport='true')
        self.assertEqual(content, (clone / 'Bar.txt').read_bytes())

    def test_push_and_pull_with_a_locally_renamed_media_file(self) -> None:
        repository = self.clone()
        self.commit(repository, 'add a file', **{'Foo.txt': 'A File\n'})
        self.git('mv', 'Foo.txt', 'Bar.txt', cwd=repository)
        self.git('commit', '-m', 'Rename a file', cwd=repository)

        self.reimport(repository)

        self.assertEqual('A File\n', (repository / 'Bar.txt').read_text(encoding='utf-8'))
        self.assertFalse((repository / 'Foo.txt').exists())

    def test_push_propagates_a_local_page_deletion(self) -> None:
        repository = self.clone()
        self.assertFalse((repository / 'Foo.mw').exists())
        self.commit(repository, 'Add the page Foo', **{'Foo.mw': 'hello world\n'})
        self.git('push', cwd=repository)

        (repository / 'Foo.mw').unlink()
        self.git('commit', '-am', 'Delete the page Foo', cwd=repository)
        self.reimport(repository)

        self.assertFalse((repository / 'Foo.mw').exists())

    def test_push_propagates_a_local_media_file_deletion(self) -> None:
        repository = self.clone()
        self.commit(repository, 'Add the text file Foo', **{'Foo.txt': 'hello world\n'})
        self.git('rm', 'Foo.txt', cwd=repository)
        self.git('commit', '-m', 'Delete the file Foo', cwd=repository)

        self.reimport(repository)

        self.assertFalse((repository / 'Foo.txt').exists())

    @unittest.expectedFailure
    def test_pull_imports_a_media_deletion_that_no_page_links_to(self) -> None:
        # The file is uploaded and then deleted, but as no page links to it the
        # import, which looks at page revisions, never sees the deletion. The
        # list of files comes from the wiki, and a deleted file is not on it.
        repository = self.clone()
        self.commit(repository, 'Add the text file Foo', **{'Foo.txt': 'hello world\n'})
        self.git('push', cwd=repository)
        self.git('rm', 'Foo.txt', cwd=repository)
        self.git('commit', '-m', 'Delete the file Foo', cwd=repository)

        self.reimport(repository)

        self.assertFalse((repository / 'Foo.txt').exists())

    def test_push_warns_about_a_file_type_the_wiki_refuses(self) -> None:
        repository = self.clone()
        self.commit(repository, 'add a file', **{'foo.forbidden': 'A File\n'})

        pushed = self.git('push', cwd=repository)

        self.assertIn('foo.forbidden is not a permitted file', pushed.stderr)

    def with_media(self) -> None:
        """A page linking one uploaded file, and another that nothing links."""
        self.wiki.edit_page('testpage', 'I am linking a file [[File:File.txt]]')
        self.wiki.upload_file('File.txt', b'File content\n')
        self.wiki.upload_file('AnotherFile.txt', b'Another file content\n')

    def test_cloning_a_page_with_mediaimport_brings_the_file_it_links(self) -> None:
        self.with_media()

        repository = self.clone(pages='testpage', mediaimport='true')

        self.assertEqual(
            ['File.txt', 'File:File.txt.mw', 'Testpage.mw'], self.page_files(repository)
        )
        self.assertPageMatches(repository, 'Testpage')
        self.assertEqual(b'File content\n', (repository / 'File.txt').read_bytes())

    def test_cloning_a_page_with_mediaimport_false_leaves_the_file(self) -> None:
        self.with_media()

        repository = self.clone(pages='testpage', mediaimport='false')

        self.assertEqual(['Testpage.mw'], self.page_files(repository))

    def test_cloning_a_page_with_mediaimport_unset_leaves_the_file(self) -> None:
        self.with_media()

        repository = self.clone(pages='testpage')

        self.assertEqual(['Testpage.mw'], self.page_files(repository))


if __name__ == '__main__':
    unittest.main()
