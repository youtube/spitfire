# Copyright 2007 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

# Default
.PHONY: all
# Build
.PHONY: build parser extensions
# Test
.PHONY: test tests unit_tests no_whitespace_tests whitespace_tests function_registry_tests optimizer_tests
# Clean up
.PHONY: clean clean_build clean_tests
# Format code
.PHONY: fix lint


PYTHON ?= python
PIP ?= pip
YAPF ?= yapf

VIRTUALENV = $(shell $(PYTHON) -c "import sys; print(hasattr(sys, 'real_prefix') or hasattr(sys, 'base_prefix'))")
ifeq ($(VIRTUALENV),True)
  PIP_INSTALL_FLAGS=
else
  PIP_INSTALL_FLAGS=--user
endif

COMPILER = $(PYTHON) scripts/spitfire-compile
CRUNNER = $(PYTHON) scripts/crunner.py
UNITTEST = $(PYTHON) -m unittest
YAPPS = $(PYTHON) third_party/yapps2/yapps2.py


all: build


build: parser extensions

parser: spitfire/compiler/parser.py

spitfire/compiler/parser.py: spitfire/compiler/parser.g third_party/yapps2/yapps2.py third_party/yapps2/yappsrt.py
	$(YAPPS) spitfire/compiler/parser.g

extensions: spitfire/runtime/_baked.so spitfire/runtime/_template.so spitfire/runtime/_udn.so

spitfire/runtime/_baked.so spitfire/runtime/_template.so spitfire/runtime/_udn.so: spitfire/runtime/_baked.c spitfire/runtime/_template.c spitfire/runtime/_udn.c
	$(PIP) install $(PIP_INSTALL_FLAGS) --editable .


fix:
	@echo; echo 'Auto-formatting code...'
	-@$(YAPF) --in-place --recursive --verify spitfire scripts

lint:
	@echo; echo 'Checking code format...'
	@$(YAPF) --diff --recursive spitfire scripts || (st=$$?; echo 'Please run "make fix" to correct the formatting errors.'; exit $$st)


test: tests

tests: unit_tests no_whitespace_tests whitespace_tests function_registry_tests optimizer_tests clean_tests

unit_tests: build
	$(UNITTEST) discover -s spitfire -p '*_test.py'

test_function_registry: build
	$(call _clean_tests)
	$(CRUNNER) -O3 --compile --function-registry-file tests/test-function-registry.cnf tests/*.txtx

no_whitespace_tests: build
	$(call _clean_tests)
	$(COMPILER) tests/*.txt tests/*.tmpl
	$(CRUNNER) tests/*.txt tests/*.tmpl
	$(COMPILER) -O1 tests/*.txt tests/*.tmpl
	$(CRUNNER) -O1 tests/*.txt tests/*.tmpl
	$(COMPILER) -O2 tests/*.txt tests/*.tmpl
	$(CRUNNER) -O2 tests/*.txt tests/*.tmpl
	$(COMPILER) -O3 tests/*.txt tests/*.tmpl
	$(CRUNNER) -O3 tests/*.txt tests/*.tmpl

whitespace_tests: build
	$(call _clean_tests)
	$(COMPILER) --preserve-optional-whitespace tests/*.txt tests/*.tmpl
	$(CRUNNER) --preserve-optional-whitespace --test-output tests/output-preserve-whitespace tests/*.txt tests/*.tmpl
	$(COMPILER) -O1 --preserve-optional-whitespace tests/*.txt tests/*.tmpl
	$(CRUNNER) -O1 --preserve-optional-whitespace --test-output tests/output-preserve-whitespace tests/*.txt tests/*.tmpl
	$(COMPILER) -O2 --preserve-optional-whitespace tests/*.txt tests/*.tmpl
	$(CRUNNER) -O2 --preserve-optional-whitespace --test-output tests/output-preserve-whitespace tests/*.txt tests/*.tmpl
	$(COMPILER) -O3 --preserve-optional-whitespace tests/*.txt tests/*.tmpl
	$(CRUNNER) -O3 --preserve-optional-whitespace --test-output tests/output-preserve-whitespace tests/*.txt tests/*.tmpl

optimizer_tests: build
	$(call _clean_tests)
	$(COMPILER) -O3 tests/*.o4txt
	$(CRUNNER) -O3 tests/*.o4txt

xhtml_tests: build
	$(call _clean_tests)
	$(COMPILER) --xspt-mode tests/*.xhtml
	$(CRUNNER) --xspt-mode --test-output tests/output-xhtml tests/*.xhtml


clean: clean_build clean_tests

clean_build:
	@find spitfire -name '*.pyc' -exec rm {} \;
	@find third_party -name '*.pyc' -exec rm {} \;
	@find spitfire -name '*.so' -exec rm {} \;
	@find third_party -name '*.so' -exec rm {} \;
	@rm -f spitfire/compiler/parser.py
	@rm -rf build
	@if [[ $$($(PIP) show spitfire | fgrep Location: | awk '{print $$2}') == $(PWD) ]]; then \
		$(PIP) uninstall --yes spitfire; \
	 fi
	@rm -rf spitfire.egg-info

clean_tests:
	$(call _clean_tests)

# Note: The define + call for clean_tests is required to force the target to
# be called before every test execution instead of once before all of them.
# The other way to do this is with recursive make calls.
define _clean_tests
	@rm -f tests/*.py
	@rm -f tests/*.pyc
	@find tests -name '*.failed' -exec rm {} \;
	@touch tests/__init__.py
endef
