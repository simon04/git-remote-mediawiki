## What is git-remote-mediawiki ?

git-remote-mediawiki is a project which aims the creation of a gate
between git and mediawiki, allowing git users to push and pull
objects from mediawiki just as one would do with a classic git
repository thanks to remote-helpers.

This is a fork of [Git-Mediawiki](https://github.com/Git-Mediawiki/Git-Mediawiki), maintained by
[simon04](https://github.com/simon04). The scripts have been rewritten from
Perl to Python; see [What changed in this fork](#what-changed-in-this-fork).

**For more information, read the [User manual](docs/User-manual.md).**

## Installation

The scripts are Python 3.14 programs that declare their dependencies inline
([PEP 723](https://peps.python.org/pep-0723/)), so the only prerequisite is
[uv](https://docs.astral.sh/uv/) — it fetches a suitable Python and the single
dependency, [mwclient](https://github.com/mwclient/mwclient), on first run.

```shell
curl -LsSf https://astral.sh/uv/install.sh | sh   # or: apt/brew/pkg install uv
```

Then, in one line, clone this repository and link its `git-*` scripts into
`~/.local/bin`, which is on `PATH` on most systems and is where uv installs
itself:

```shell
git clone https://github.com/simon04/git-remote-mediawiki ~/.local/share/git-remote-mediawiki && mkdir -p ~/.local/bin && ln -sf ~/.local/share/git-remote-mediawiki/git-* ~/.local/bin/
```

If you keep your checkouts in `~/src`, or want to hack on the scripts, clone
there instead and link from there:

```shell
git clone https://github.com/simon04/git-remote-mediawiki ~/src/git-remote-mediawiki
mkdir -p ~/.local/bin
ln -sf ~/src/git-remote-mediawiki/git-* ~/.local/bin/
```

Git finds `git-remote-mediawiki`, `git-mw` and `git-clone-mediawiki` anywhere
on `PATH`, so any other directory on it works as well, and so does putting the
checkout itself on `PATH`. A `git pull` in the checkout updates the commands.

See the [User manual](docs/User-manual.md) for the details.

## Usage

```shell
git mw setup                  # asks what you want and clones it
git clone-mediawiki https://de.wikipedia.org/wiki/Innsbruck   # one page
git clone-mediawiki https://de.wikipedia.org/wiki/Kategorie:JavaScript-Engine
git clone mediawiki::http://example.com/wiki/
git mw preview Some_page.mw
```

To try the scripts from a checkout without installing them, put it first on
`PATH` for one command:

```shell
PATH="$PWD:$PATH" git clone mediawiki::http://example.com/wiki/
```

## Development

```shell
# Lint, format and type-check with the versions pinned in uv.lock
uv run ruff check .
uv run ruff format .          # --check to verify without rewriting, as CI does
uv run ty check --extra-search-path . --extra-search-path t

# Run the tests. They need no wiki: they drive the real scripts against an
# in-process stand-in for one, in t/fakewiki.py
python3 -m unittest discover --start-directory t --verbose
```

See [the test suite's README](t/README.md) for how the stand-in works and how
to add a test.

## What changed in this fork

Upstream had been looking for a new maintainer since [issue #33](https://github.com/Git-Mediawiki/Git-Mediawiki/issues/33).
This fork picks it up and, so far:

* rewrites `git-remote-mediawiki`, `git mw` and the test helper from Perl to
  Python 3.14, replacing `MediaWiki::API` with
  [mwclient](https://github.com/mwclient/mwclient). The scripts declare their
  own dependencies inline, so there is nothing to install but
  [uv](https://docs.astral.sh/uv/).
* adds `git mw setup`, a questionnaire that checks each answer against the wiki
  and then runs the `git clone` it describes.
* adds `git clone-mediawiki`, which clones a page or a category given its
  address as shown in the browser.
* documents [using it with Wikipedia](docs/Wikipedia.md), which needs a bot
  password rather than an account password.
* fixes a handful of long-standing bugs on the way, among them page slices one
  title over the API limit, and quotes leaking into every pushed edit summary.

## Who are we ?

Git-Mediawiki was essentially developed by [Ensimag](http://ensimag.grenoble-inp.fr/) students (see the logs for the detailed list of authors), supervised  by [Matthieu Moy](https://matthieu-moy.fr/), with the help of the [git community](http://git.kernel.org/).

Do not hesitate to open an issue if you have any questions about the project.

## Links

* [User manual](docs/User-manual.md)
* [Using git-remote-mediawiki with Wikipedia](docs/Wikipedia.md)
* [Bug tracking](https://github.com/simon04/git-remote-mediawiki/issues)
* [Implementation documentation](docs/Implementation-documentation.md)
   * [Remote helpers](docs/Remote-Helpers.md)
   * [Fast import & Fast export](docs/Fast-Import-&-Fast-Export.md)
   * Storing metadata : [Git notes](docs/Git-notes.md)
   * [Data-encoding](docs/Data-encoding.md)
* [Further Developing](docs/Further-developing.md)

## Similar projects

Our project wants to be transparent to wiki users and transplantable on any wiki without having to change anything server-side. A simple git clone on a mediawiki would initialize a repository on your side and you would be able to interact with the wiki without bothering classic users.

But there are other options for archiving wikis and git-based wikis:

 * [GitHub](https://github.com/) and [ikiwiki](http://ikiwiki.info/)
   propose solutions for git-based wikis.
 * The [WikiTeam][] has scripts and programs to dump Mediawiki sites,
   although not to git, and readonly.

[WikiTeam]: https://github.com/WikiTeam/wikiteam
