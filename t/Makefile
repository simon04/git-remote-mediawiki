#
# Copyright (C) 2012
#     Charles Roussel <charles.roussel@ensimag.imag.fr>
#     Simon Cathebras <simon.cathebras@ensimag.imag.fr>
#     Julien Khayat <julien.khayat@ensimag.imag.fr>
#     Guillaume Sasdy <guillaume.sasdy@ensimag.imag.fr>
#     Simon Perrat <simon.perrat@ensimag.imag.fr>
#
## Test git-remote-mediawiki

# The default target of this Makefile is...
all:: unittest

T = $(wildcard t[0-9][0-9][0-9][0-9]-*.sh)

.PHONY: help unittest test clean all

help:
	@echo 'Run "$(MAKE) unittest" for the Python tests, which need no wiki'
	@echo 'Run "$(MAKE) test" for the shell tests, which need a local wiki'
	@echo 'Run "$(MAKE) clean" to remove trash folders'

unittest:
	python3 -m unittest discover --start-directory . --verbose

test:
	@for t in $(T); do \
		echo "$$t"; \
		"./$$t" --verbose || exit 1; \
	done

clean:
	$(RM) -r 'trash directory'.*
