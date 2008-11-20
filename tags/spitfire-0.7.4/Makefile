ifndef PYTHONPATH
	export PYTHONPATH = ../yapps2
endif

ifndef YAPPS
	export YAPPS = ../yapps2/yapps2.py
endif

CRUNNER = python2.4 scripts/crunner.py
COMPILER = python2.4 scripts/spitfire-compile

spitfire/compiler/parser.py: spitfire/compiler/parser.g
	$(YAPPS) spitfire/compiler/parser.g

parser: spitfire/compiler/parser.py

all: parser

.PHONY : test_function_registry
test_function_registry: parser
	$(CRUNNER) -O3 --compile --test-input tests/input/search_list_data.pye -qt tests/test-function-registry.txtx tests/i18n-7.txtx --function-registry-file tests/test-function-registry.cnf

.PHONY : no_whitespace_tests
no_whitespace_tests: clean_tests parser
	$(COMPILER) tests/*.txt tests/*.tmpl
	$(CRUNNER) --test-input tests/input/search_list_data.pye -qt tests/*.txt tests/*.tmpl
	$(COMPILER) -O1 tests/*.txt tests/*.tmpl
	$(CRUNNER) -O1 --test-input tests/input/search_list_data.pye -qt tests/*.txt tests/*.tmpl
	$(COMPILER) -O2 tests/*.txt tests/*.tmpl
	$(CRUNNER) -O2 --test-input tests/input/search_list_data.pye -qt tests/*.txt tests/*.tmpl
	$(COMPILER) -O3 tests/*.txt tests/*.tmpl
	$(CRUNNER) -O3 --test-input tests/input/search_list_data.pye -qt tests/*.txt tests/*.tmpl

.PHONY : whitespace_tests
whitespace_tests: clean_tests parser
	$(COMPILER) --preserve-optional-whitespace tests/*.txt tests/*.tmpl
	$(CRUNNER) --preserve-optional-whitespace --test-input tests/input/search_list_data.pye --test-output output-preserve-whitespace -qt tests/*.txt tests/*.tmpl
	$(COMPILER) -O1 --preserve-optional-whitespace tests/*.txt tests/*.tmpl
	$(CRUNNER) -O1 --preserve-optional-whitespace --test-input tests/input/search_list_data.pye --test-output output-preserve-whitespace -qt tests/*.txt tests/*.tmpl
	$(COMPILER) -O2 --preserve-optional-whitespace tests/*.txt tests/*.tmpl
	$(CRUNNER) -O2 --preserve-optional-whitespace --test-input tests/input/search_list_data.pye --test-output output-preserve-whitespace -qt tests/*.txt tests/*.tmpl
	$(COMPILER) -O3 --preserve-optional-whitespace tests/*.txt tests/*.tmpl
	$(CRUNNER) -O3 --preserve-optional-whitespace --test-input tests/input/search_list_data.pye --test-output output-preserve-whitespace -qt tests/*.txt tests/*.tmpl

.PHONY : test_opt
test_opt: clean_tests parser
	$(COMPILER) -O4 tests/*.txt tests/*.tmpl tests/*.o4txt
	$(CRUNNER) -O4 --test-input tests/input/search_list_data.pye -qt tests/*.txt tests/*.tmpl tests/*.o4txt
	$(COMPILER) -O4 --preserve-optional-whitespace tests/*.txt tests/*.tmpl tests/*.o4txt
	$(CRUNNER) -O4 --preserve-optional-whitespace --test-input tests/input/search_list_data.pye --test-output output-preserve-whitespace -qt tests/*.txt tests/*.tmpl tests/*.o4txt


.PHONY : xhtml_tests
xhtml_tests: clean_tests parser
	$(COMPILER) --xspt-mode tests/*.xhtml
	$(CRUNNER) --xspt-mode --test-input tests/input/search_list_data.pye --test-output output-xhtml -qt tests/*.xhtml

.PHONY : tests
tests: no_whitespace_tests whitespace_tests test_function_registry test_opt


.PHONY : clean
clean: clean_tests
	@find . -name '*.pyc' -exec rm {} \;
	@rm -f spitfire/compiler/parser.py
	@rm -rf build

.PHONY : clean_tests
clean_tests:
	@rm -f tests/*.py
	@rm -f tests/*.pyc
	@find tests -name '*.failed' -exec rm {} \;
	@touch tests/__init__.py

.PHONE : clean_all
clean_all : clean clean_tests
