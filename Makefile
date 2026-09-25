SHELL := /bin/bash
PYTHON ?= python3
PY := .venv/bin/python

.PHONY: help venv test

help: ## List targets
	@grep -E '^[a-z-]+:.*?##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' | expand -t16

venv: ## Create .venv with runtime and dev dependencies
	$(PYTHON) -m venv .venv && $(PY) -m pip install --quiet --upgrade pip && $(PY) -m pip install --quiet -e '.[dev]'

test: ## Run the unit tests
	$(PY) -m pytest -q
