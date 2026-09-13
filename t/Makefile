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
all:: test

.PHONY: help test clean all

help:
	@echo 'Run "$(MAKE) test" to run the tests. They need no wiki.'
	@echo 'Run "$(MAKE) clean" to remove what they leave behind'

test:
	python3 -m unittest discover --start-directory . --verbose

clean:
	$(RM) -r __pycache__
