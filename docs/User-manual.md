## Installation

You need to have Git installed on your machine. See the [help with setup for Windows](http://help.github.com/win-set-up-git/), [Mac](http://help.github.com/mac-set-up-git/) or [Linux](http://help.github.com/linux-set-up-git/).

### Dependencies

The scripts are Python 3.14 programs that declare their dependencies inline
([PEP 723](https://peps.python.org/pep-0723/)), so the only thing you need to
install is [uv](https://docs.astral.sh/uv/):

```shell
# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

uv is also packaged for most distributions (`apt install uv`, `brew install uv`,
`emerge dev-python/uv`, `pkg install uv`, ...).

The first run downloads a suitable Python interpreter and the only third-party
dependency, [mwclient](https://github.com/mwclient/mwclient), into a cached
environment; later runs reuse it.

### git-remote-mediawiki

git-remote-mediawiki began life as `contrib/mw-to-git` in Git's own source tree, and was installed along with Git. It is no longer carried there, and this fork is a standalone Python rewrite, so there is nothing to build and no dependency on Git's build system -- only on having a reasonably recent `git` to run against.

#### Installing from source

Git runs a `git-<name>` program it finds anywhere on `PATH` as `git <name>`,
and a `git-remote-<scheme>` one as the helper for `<scheme>::` URLs. So
installing means getting the three `git-*` scripts of a checkout onto `PATH`,
in one of two ways.

Link them into a directory that is already on `PATH`, such as `~/.local/bin`:

```shell
git clone https://github.com/simon04/git-remote-mediawiki ~/.local/share/git-remote-mediawiki && mkdir -p ~/.local/bin && ln -sf ~/.local/share/git-remote-mediawiki/git-* ~/.local/bin/
```

Or put the checkout itself on `PATH`, for instance in `~/.bashrc`:

```shell
export PATH="$HOME/.local/share/git-remote-mediawiki:$PATH"
```

Either way, a `git pull` in the checkout updates the commands. Link rather than
copy: the scripts import `git_mediawiki.py`, and find their translations, next
to the file a link points at, so a copy needs `git_mediawiki.py` copied beside
it too. Whatever the name, keep it without a suffix: `git-remote-mediawiki`,
_not_ `git-remote-mediawiki.py`.

## Getting started with git-remote-mediawiki

Then, the first operation you should do is cloning the remote mediawiki. To do so, run the command

    git clone mediawiki::http://yourwikiadress.com

You can commit your changes locally as usual with the command

    git commit

You can pull the last revision from mediawiki with the command 

    git pull --rebase

You can push the changes you commited as usual with the command

    git push

It is strongly recommanded to run `git pull --rebase` after each `git push`.

Knowing those commands, you can now edit your wiki with your favorite text editor!

## Partial import of a Wiki
### Limit the pages to be imported

The quickest way to clone a single page, or every page of a category, is to hand its address, as shown in the browser, to `git clone-mediawiki`:

    git clone-mediawiki https://de.wikipedia.org/wiki/Innsbruck
    git clone-mediawiki https://de.wikipedia.org/wiki/Kategorie:JavaScript-Engine

It finds the wiki's `api.php` from the page, asks the wiki whether the title is a category, and runs the `git clone` described below; `--dry-run` prints that command instead.


If you don't want to clone the whole wiki, you can import only some pages with:

    git clone -c remote.origin.pages='A_page Another_page' mediawiki::http://yourwikiadress.com

and/or select the content of MediaWiki Categories with:

    git clone -c remote.origin.categories='First Second' mediawiki::http://yourwikiadress.com

By default, only the main namespace is inspected. But you can also specify other namespaces with the [following patchset](https://github.com/Git-Mediawiki/Git-Mediawiki/issues/10):

    git clone -c remote.origin.namespaces='(Main) Talk' mediawiki::http://yourwikiadress.com

### Shallow imports

It is also possible to import only the last revision of a wiki. This is done using the `remote.origin.shallow` configuration variable. To set it during a clone, use:

    git -c remote.origin.shallow=true clone mediawiki::http://example.com/wiki/

Alternatively, you may let clone write the value to the `.git/config` file to have further `git fetch` import only the last revision of each page too with

    git clone -c remote.origin.shallow=true mediawiki::http://example.com/wiki/

(i.e. `-c` option used after `clone` in the command)

## Authentication

Some wiki require login/password. You can specify a login and password using the `remote.origin.mwLogin` and `remote.origin.mwPassword` configuration variables. If you need to do that at clone time, the best way is

    git init new-repo
    chmod 600 .git/config # you're going to put a password there
                          # so don't keep it world-readable!
    cd new-repo
    git remote add origin mediawiki::http://example.com/
    git config remote.origin.mwLogin 'UserName'
    git config remote.origin.mwPassword 'PassWord'
    git pull
    git push

If you wiki requires specifying a domain when logging in (if you use LDAP authentication for instance), then you can set `remote.origin.mwDomain` to the corresponding value.

Rather than storing the password in `.git/config`, you can set only `remote.origin.mwLogin` and let Git ask for the password through `git credential`, which hands it to whichever credential helper you have configured.

Wikimedia wikis, Wikipedia among them, will not accept a main-account password here at all; they need a bot password. See [Using git-remote-mediawiki with Wikipedia](Wikipedia.md).

## Previewing changes

(This is work in progress, you need to apply Benoit Person's patches to get this)

You can preview a page without actually pushing it to the wiki using "git mw preview". Run "git mw help" for more information.

## Configuring and understanding how `push` works

By default, when running `git push` to a MediaWiki, Git will update the metadata (remote reference, and the last imported MediaWiki revision stored in notes) during push to reflect the fact that your local revisions correspond to the exported MediaWiki revisions. This way, the next `git pull` will already know that the new revisions on MediaWiki come from your repository, and will not have to re-import them.

While this is convenient, this comes with a drawback: your view of history is the one you've created from Git, and other users cloning the MediaWiki will have a slightly different view of history. If your push loses data (because MediaWiki cannot store a few things that Git can), you may not notice it, but other users will. Also, this means you have no chance to have the same commit identifiers as other cloners of the MediaWiki. An alternative is to set the `mediawiki.dumbPush` configuration variable to `true` (if needed, this can also be done on a per-remote basis with `remote.<name>.dumbPush`). If you do so, `git push` will not touch the MediaWiki metadata, and will ask you to reimport history after a successful push, typically with `git pull --rebase`. For those who know `git svn`: in this mode, `git push; git pull --rebase` is the equivalent of `git svn dcommit`.

## Uploads (files and images)

To include uploaded files, set the two config options `mediaimport` and `mediaexport`:
~~~
git config --bool remote.origin.mediaimport true
git config --bool remote.origin.mediaexport true
~~~

## Optimizing git fetch

By default, git-remote-mediawiki will list new revisions for each wiki page (`remote.<name>.fetchStrategy` set to `by_page`). This is the most efficient method when cloning a small subset of a very active wiki. On the other hand, fetching from a wiki with little activity but many pages is long (the tool has to query every page even to say "Everything up to date").

One can set `remote.<name>.fetchStrategy` to `by_rev`. Then, git-remote-mediawiki will query the whole wiki for new revisions, and will filter-out revisions that should not be fetched because they do not touch tracked pages. In this case, for example, fetching from an up-to-date wiki is done in constant time (not O(number of pages)).

## Issues with SSL, self-signed or unrecognized certificates

By default, git-remote-mediawiki verifies the SSL certificate of the wiki.

If your wiki uses a self-signed certificate, git-remote-mediawiki won't be able to connect to it. There are several solutions:

* The insecure way: disable SSL verification:

        CURL_CA_BUNDLE= git pull
     
* The more secure way: download, install, and trust the certificate. This won't give you 100% guarantee that the certificate is correct, but if an attacker tries to spoof the hostname after you've downloaded the certificate, you should notice it:

        echo | openssl s_client -showcerts -connect wiki.example.com:443 > certs.pem
        REQUESTS_CA_BUNDLE=certs.pem git pull

## Cloning mediawiki repositories

It may happen that you need to clone a repository that was created from a mediawiki instance. Just a regular clone will not be enough, because there is extra metadata in the repository that is not cloned by default. Furthermore, you will need to synchronize the configuration. For example, I had to do this to completely clone my repository:

```
git clone orig.example.com:mirror/wiki.example.com
cd wiki.example.com
git fetch origin refs/notes/*:refs/notes/*
git fetch origin refs/mediawiki/*:refs/mediawiki/*
git remote set-url origin mediawiki::http://wiki.example.com/
git config remote.origin.fetchstrategy by_rev
git config remote.origin.mediaimport true
git pull
```

The configuration will, of course, vary according to your original configuration.