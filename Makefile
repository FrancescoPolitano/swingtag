SHELL := /bin/bash
PYTHON ?= python3
PY := .venv/bin/python

EXAMPLE ?= restaurant

.PHONY: help venv test build demo plan destroy verify fmt plates

help: ## List targets
	@grep -E '^[a-z-]+:.*?##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' | expand -t16

venv: ## Create .venv with runtime and dev dependencies
	$(PYTHON) -m venv .venv && $(PY) -m pip install --quiet --upgrade pip && $(PY) -m pip install --quiet -e '.[dev]'

test: ## Run the unit tests
	$(PY) -m pytest -q

TF := terraform -chdir=examples/$(EXAMPLE)

build: ## Build the Lambda package in build/lambda
	./scripts/build_lambda.sh

demo: test build ## Deploy an example: make demo EXAMPLE=restaurant|nursery|exhibition
	$(TF) init -input=false
	$(TF) apply -input=false -auto-approve
	@$(TF) output pages

plan: build ## Show the plan of an example
	$(TF) init -input=false
	$(TF) plan -input=false

destroy: build ## Remove every resource of an example (the package is read even on destroy)
	$(TF) destroy -input=false -auto-approve

verify: ## Live checks of a deployed example
	@$(TF) output -json pages >/dev/null 2>&1 && [ "$$($(TF) output -json pages)" != "{}" ] || { echo "examples/$(EXAMPLE) is not deployed: run make demo EXAMPLE=$(EXAMPLE) first"; exit 1; }
	./scripts/verify.sh "$$($(TF) output -raw base_url)" \
		"$$($(TF) output -json pages | $(PY) -c 'import json,sys; print(sorted(json.load(sys.stdin).values())[0].rsplit("/", 1)[1])')"

fmt: build ## Format the Terraform code and validate the example
	terraform fmt -recursive
	$(TF) init -input=false -backend=false >/dev/null
	$(TF) validate

plates: ## Printable QR sheet of a deployed example (needs its Terraform outputs)
	$(PY) scripts/plates.py "$$(terraform -chdir=examples/$(EXAMPLE) output -raw bucket)" \
		"$$(terraform -chdir=examples/$(EXAMPLE) output -raw base_url)" -o build/plates-$(EXAMPLE).pdf
