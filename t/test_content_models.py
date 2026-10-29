"""Pages that are not wikitext: JavaScript, CSS, JSON and Lua modules."""

import unittest

from gitmwtest import GitMediaWikiTestCase


class ContentModelTest(GitMediaWikiTestCase):
    def test_clone_names_files_by_content_model(self) -> None:
        self.wiki.edit_page('MediaWiki:Gadget-Stockphoto.js', 'var stockphoto = {};')
        self.wiki.edit_page('MediaWiki:Gadget-Stockphoto.css', '.stockphoto { color: red; }')
        self.wiki.edit_page('User:Foo/common.js', 'mw.log("hello");')
        self.wiki.edit_page('MediaWiki:Gadget-Stockphoto.json', '{"stockphoto": true}')
        self.wiki.edit_page('Module:Arguments', 'local p = {}\nreturn p')
        self.wiki.edit_page('Module:Arguments/doc', 'How to use the module')

        repository = self.clone(
            pages='MediaWiki:Gadget-Stockphoto.js MediaWiki:Gadget-Stockphoto.css'
            ' MediaWiki:Gadget-Stockphoto.json User:Foo/common.js'
            ' Module:Arguments Module:Arguments/doc'
        )

        self.assertEqual(
            [
                'MediaWiki:Gadget-Stockphoto.css',
                'MediaWiki:Gadget-Stockphoto.js',
                'MediaWiki:Gadget-Stockphoto.json',
                'Module:Arguments%2Fdoc.mw',
                'Module:Arguments.lua',
                'User:Foo%2Fcommon.js',
            ],
            self.page_files(repository),
        )
        self.assertRepositoryMatchesWiki(
            repository, [title for title in self.wiki.titles() if title != 'Main Page']
        )
        self.assertNothingUnhandled()

    def test_push_edits_the_page_a_file_stands_for(self) -> None:
        self.wiki.edit_page('MediaWiki:Gadget-Stockphoto.js', 'var stockphoto = {};')
        self.wiki.edit_page('Module:Arguments', 'local p = {}\nreturn p')
        repository = self.clone(pages='MediaWiki:Gadget-Stockphoto.js Module:Arguments')

        self.commit(
            repository,
            'edit the gadget and the module',
            **{
                'MediaWiki:Gadget-Stockphoto.js': 'var stockphoto = { edited: true };\n',
                'Module:Arguments.lua': 'local p = { edited = true }\nreturn p\n',
                'Module:New.lua': 'return {}\n',
            },
        )
        self.git('push', cwd=repository)

        self.assertEqual(
            'var stockphoto = { edited: true };',
            self.wiki_page('MediaWiki:Gadget-Stockphoto.js').text,
        )
        self.assertEqual(
            'local p = { edited = true }\nreturn p', self.wiki_page('Module:Arguments').text
        )
        self.assertEqual('return {}', self.wiki_page('Module:New').text)
        self.assertNotIn('Module:Arguments.lua', self.wiki.titles())
        self.assertNothingUnhandled()


if __name__ == '__main__':
    unittest.main()
