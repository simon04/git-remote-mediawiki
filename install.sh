#!/bin/sh
# Link the git-* scripts of this checkout into a directory on PATH, by default
# ~/.local/bin, so that git finds them as git mw, git clone-mediawiki and the
# mediawiki:: remote helper. Run it from the root of the checkout:
#
#     ./install.sh [<directory>]
#
# Links rather than copies, so a git pull here updates the commands.

set -eu

target=${1:-$HOME/.local/bin}
mkdir -p "$target"
for script in "$PWD"/git-*; do
	ln -sfv "$script" "$target/"
done

case ":$PATH:" in
*":$target:"*) ;;
*) echo "warning: $target is not on PATH; git will not find the commands" >&2 ;;
esac
