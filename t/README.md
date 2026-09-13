# Testing git-remote-mediawiki

The tests are Python, and run against a MediaWiki that lives inside the test
process. They need no web server, no PHP and no MediaWiki install. From the top
of the repository:

```shell
python3 -m unittest discover --start-directory t --verbose
```

or from here:

```shell
python3 -m unittest discover --verbose
```

## How they work

`fakewiki.py` answers the API calls the bridge makes. Tests change its contents
directly, through `edit_page`, `delete_page` and `upload_file`; only the code
under test goes over HTTP.

It implements what the bridge asks for and refuses anything else, rather than
returning a plausible empty result. `assertNothingUnhandled` fails a test that
provoked such a refusal. A fake that guesses is worse than no fake, because the
confidence it gives is not earned.

`gitmwtest.py` gives each test an empty wiki and a scratch directory, and runs
the real `git` binary against the real scripts. Nothing imports the code under
test, so the remote-helper protocol, the lookup of `git-remote-mediawiki` on
`PATH`, and fast-import are all exercised as they are in use.

## Writing a test

```python
class MyTest(GitMediaWikiTestCase):
    def test_something(self) -> None:
        self.wiki.edit_page('Foo', 'contents')
        repository = self.clone()
        self.assertRepositoryMatchesWiki(repository)
```

| Helper | Does |
| --- | --- |
| `self.clone(**config)` | Clones the wiki, passing keywords as `remote.origin.<name>` |
| `self.git(...)` | Runs git in the repository, failing the test if it exits non-zero |
| `self.commit(repository, message, **files)` | Writes files and commits them |
| `self.page_files(repository)` | The tracked files, which is what the pages became |
| `self.assertPageMatches(repository, title)` | One page holds the wiki's content |
| `self.assertRepositoryMatchesWiki(repository, titles=None)` | Those pages, and no others, hold it |
| `self.assertNothingUnhandled()` | The fake was not asked anything it does not implement |

## Against a real MediaWiki

Nothing does this yet, and it is the gap worth closing: every difference
between `fakewiki.py` and a real wiki is a way for these tests to pass while
the bridge is broken. Five such differences turned up while the shell tests
were being ported, among them that MediaWiki trims trailing whitespace when it
saves, which is what makes a page deleted through git stay deleted.

`install_wiki.py` stands up a real MediaWiki with lighttpd and PHP, and is kept
for that purpose:

```shell
./install_wiki.py install
./install_wiki.py reset       # database back to just after installation
./install_wiki.py delete

./install_wiki.py --help      # port, version, administrator
```

It is stdlib only, so it runs under plain `python3` like the tests do.
