# Copyright 2007 The Spitfire Authors. All Rights Reserved.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

# Default
.PHONY: all
# Build
.PHONY: build parser extensions
# Test
.PHONY: tests unit_tests no_whitespace_tests whitespace_tests test_function_registry test_opt
# Clean up
.PHONY: clean clean_build clean_tests
# Format code
.PHONY: fix lint


PYTHON ?= python
PIP ?= pip
YAPF ?= yapf

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
	$(PIP) install --user --editable .


fix:
	@echo; echo 'Auto-formatting code...'
	-@$(YAPF) --in-place --recursive --verify spitfire scripts

lint:
	@echo; echo 'Checking code format...'
	@$(YAPF) --diff --recursive spitfire scripts || (st=$$?; echo 'Please run "make fix" to correct the formatting errors.'; exit $$st)


tests: unit_tests no_whitespace_tests whitespace_tests test_function_registry test_opt

unit_tests: build
	$(UNITTEST) discover -s spitfire -p '*_test.py'

test_function_registry: clean_tests build
	$(CRUNNER) -O3 --compile --test-input tests/input/search_list_data.pye -qt tests/test-function-registry.txtx tests/i18n-7.txtx --function-registry-file tests/test-function-registry.cnf

no_whitespace_tests: clean_tests build
	$(COMPILER) tests/*.txt tests/*.tmpl
	$(CRUNNER) --test-input tests/input/search_list_data.pye -qt tests/*.txt tests/*.tmpl
	$(COMPILER) -O1 tests/*.txt tests/*.tmpl
	$(CRUNNER) -O1 --test-input tests/input/search_list_data.pye -qt tests/*.txt tests/*.tmpl
	$(COMPILER) -O2 tests/*.txt tests/*.tmpl
	$(CRUNNER) -O2 --test-input tests/input/search_list_data.pye -qt tests/*.txt tests/*.tmpl
	$(COMPILER) -O3 tests/*.txt tests/*.tmpl
	$(CRUNNER) -O3 --test-input tests/input/search_list_data.pye -qt tests/*.txt tests/*.tmpl

whitespace_tests: clean_tests build
	$(COMPILER) --preserve-optional-whitespace tests/*.txt tests/*.tmpl
	$(CRUNNER) --preserve-optional-whitespace --test-input tests/input/search_list_data.pye --test-output output-preserve-whitespace -qt tests/*.txt tests/*.tmpl
	$(COMPILER) -O1 --preserve-optional-whitespace tests/*.txt tests/*.tmpl
	$(CRUNNER) -O1 --preserve-optional-whitespace --test-input tests/input/search_list_data.pye --test-output output-preserve-whitespace -qt tests/*.txt tests/*.tmpl
	$(COMPILER) -O2 --preserve-optional-whitespace tests/*.txt tests/*.tmpl
	$(CRUNNER) -O2 --preserve-optional-whitespace --test-input tests/input/search_list_data.pye --test-output output-preserve-whitespace -qt tests/*.txt tests/*.tmpl
	$(COMPILER) -O3 --preserve-optional-whitespace tests/*.txt tests/*.tmpl
	$(CRUNNER) -O3 --preserve-optional-whitespace --test-input tests/input/search_list_data.pye --test-output output-preserve-whitespace -qt tests/*.txt tests/*.tmpl

test_opt: clean_tests build
	$(COMPILER) -O4 tests/*.txt tests/*.tmpl tests/*.o4txt
	$(CRUNNER) -O4 --test-input tests/input/search_list_data.pye -qt tests/*.txt tests/*.tmpl tests/*.o4txt
	$(COMPILER) -O4 --preserve-optional-whitespace tests/*.txt tests/*.tmpl tests/*.o4txt
	$(CRUNNER) -O4 --preserve-optional-whitespace --test-input tests/input/search_list_data.pye --test-output output-preserve-whitespace -qt tests/*.txt tests/*.tmpl tests/*.o4txt

xhtml_tests: clean_tests build
	$(COMPILER) --xspt-mode tests/*.xhtml
	$(CRUNNER) --xspt-mode --test-input tests/input/search_list_data.pye --test-output output-xhtml -qt tests/*.xhtml


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
	@rm -f tests/*.py
	@rm -f tests/*.pyc
	@find tests -name '*.failed' -exec rm {} \;
	@touch tests/__init__.py
