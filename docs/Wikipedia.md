# Using git-remote-mediawiki with Wikipedia

Wikipedia is a MediaWiki like any other, but it is large, live, and has its own
rules about how a program may log in. This page collects what you need to know
before pointing git-remote-mediawiki at it.

Everything below was checked against `en.wikipedia.org`, running MediaWiki
1.47.0-wmf.19 at the time of writing. Other Wikimedia wikis behave the same way;
other language editions differ only in their hostname.

## The short way: `git mw setup`

`git mw setup` asks the questions this page answers, checks each answer against
the wiki, and then runs the `git clone` that follows from them. It prints that
command and waits for confirmation before running it, so it is also a way of
finding out what to type.

```shell
git mw setup
```

It needs a terminal, since it prompts. Everything it does can be done by hand
with the rest of this page.

## The URL

The remote URL is `mediawiki::` followed by the address holding `api.php`. For
the English Wikipedia the API lives at `https://en.wikipedia.org/w/api.php`, so
the address is:

```shell
git clone mediawiki::https://en.wikipedia.org/w wikipedia
```

Note the single `/w` — not `/wiki`, which is the path articles are served
under.

## Clone only the pages you want

The command above clones *every* page of the wiki, which on Wikipedia means
millions of them. In practice you always want a subset. See
[Partial import of a Wiki](User-manual.md#partial-import-of-a-wiki) for the
details; the short version is:

```shell
# individual pages; values are separated by whitespace, so a space in a
# title is written as an underscore
git clone -c remote.origin.pages="Git Linux_kernel" mediawiki::https://en.wikipedia.org/w wikipedia

# or everything in a category
git clone -c remote.origin.categories="Version_control_systems" mediawiki::https://en.wikipedia.org/w wikipedia
```

## Logging in needs a bot password

git-remote-mediawiki authenticates with the API's `action=login`. Wikipedia's own
documentation for that module says:

> Log in and get authentication cookies. This action should only be used in
> combination with `Special:BotPasswords`; use for main-account login is
> deprecated and may fail without warning.

So your ordinary account password will not reliably work. Create a bot password
at [Special:BotPasswords](https://en.wikipedia.org/wiki/Special:BotPasswords)
and give it the grants you need:

| Grant | Needed for |
| --- | --- |
| Edit existing pages | `git push` of a change to a page that already exists |
| Create, edit, and move pages | `git push` that adds a new page |
| Upload new files | pushing media files, see below |

You end up with a login name of the form `YourName@labelyoupicked` and a
generated password.

## Setting the credentials

Point the remote at the bot password's login name:

```shell
git config remote.origin.mwLogin 'YourName@labelyoupicked'
```

Leave the password out of the configuration. git-remote-mediawiki asks
`git credential` for it, so it is prompted for once and then kept by whatever
credential helper you have configured, filed under the remote's URL:

```shell
git config --global credential.helper osxkeychain   # macOS
git config --global credential.helper libsecret     # GNOME
```

There is also a `remote.<name>.mwPassword` setting, but it stores the password
in cleartext in `.git/config`; prefer the credential helper. `mwDomain` is for
wikis behind LDAP and is not used by Wikipedia.

## Committing and pushing

Commit as normal. The **subject line of the commit message becomes the edit
summary** on the wiki, so write it for the page history rather than for your
own log.

```shell
git commit -am "Fix a typo in the lead paragraph"
git push
```

Pushing only works to the branch `master`, which is what a clone gives you. If
you are on a branch with another name you need to say so explicitly, otherwise
the push is rejected with *"Only push to the branch 'master' is supported on a
MediaWiki"*:

```shell
git push origin main:master
```

You do not need to pull after a successful push: by default git-remote-mediawiki
updates the notes and the remote reference itself, so the next `git pull`
already knows those revisions came from you. That changes if you set
`mediawiki.dumbPush`, which is described in
[Configuring and understanding how `push` works](User-manual.md#configuring-and-understanding-how-push-works).

## Page names are not file names

Titles are mangled so they can be file names: a space becomes `_` and a `/`
becomes `%2F`.

| Wiki title | File in your repository |
| --- | --- |
| `Git` | `Git.mw` |
| `Linux kernel` | `Linux_kernel.mw` |
| `User:simon04/sandbox` | `User:simon04%2Fsandbox.mw` |

Edit the file in place. Renaming it is not a page move: it is pushed as a
delete of the old title and a creation of the new one.

## Media files

`mediaexport` is on by default, which means **any file you commit that does not
end in `.mw` is pushed as a file upload**. Uploads need their own grant, and
Wikipedia only accepts a fixed set of types:

```
tiff tif png gif jpg jpeg webp xcf pdf mid ogg ogv svg djvu oga flac opus wav
webm mp3 midi mpg mpeg
```

A `notes.txt` committed next to your pages will therefore be refused with
*"notes.txt is not a permitted file on this wiki"*. For a text-only workflow,
turn the whole thing off:

```shell
git config --bool remote.origin.mediaexport false
```

Note also that most freely-licensed media belongs on Wikimedia Commons rather
than on the English Wikipedia.

## Rate limits, and editing responsibly

git-remote-mediawiki makes **one API edit per changed file per commit**. Pushing a
branch of twenty commits produces twenty separate edits, each appearing on its
own in the page history and in the watchlists of everyone following the page.
Wikipedia rate-limits editing, and this pattern is, by any reasonable reading,
automated editing.

Before pointing this at article space:

- Try it on your own sandbox first, for example by cloning with
  `-c remote.origin.pages="User:YourName/sandbox"`.
- Read [Wikipedia:Bot policy](https://en.wikipedia.org/wiki/Wikipedia:Bot_policy).
  Unapproved automated editing gets accounts blocked.

If somebody edits a page on the wiki between your last pull and your push, the
API reports an edit conflict and the push is rejected as a non-fast-forward.
A commit touching several pages may have pushed some of them before it stops.
Recover with `git pull --rebase` and push again.

## User-Agent

Requests identify themselves as:

```
git-remote-mediawiki/0.01 (https://github.com/simon04/git-remote-mediawiki) mwclient/0.11.0 (...)
```

That names the tool but carries no contact address, which
[Wikimedia's User-Agent policy](https://meta.wikimedia.org/wiki/User-Agent_policy)
asks for. For anything beyond occasional sandbox edits, consider adding your
username or an email address to `clients_useragent` in `git_mediawiki.py`.
