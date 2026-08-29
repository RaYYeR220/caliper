# Every target here is also reachable through the `caliper` CLI, so a reviewer on Windows or
# without make can run the same things. See REPRODUCE.md.

PY := .venv/bin/python
ifeq ($(OS),Windows_NT)
PY := .venv/Scripts/python.exe
endif

.DEFAULT_GOAL := help
.PHONY: help install test lint typecheck check data-verify eval eval-live baseline report clean

help: ## Show the targets that matter
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

install: ## Create the virtualenv and install the project
	uv venv --python 3.12
	uv pip install -e ".[dev]"

test: ## Run the full test suite
	$(PY) -m pytest

lint: ## Style and static checks
	$(PY) -m ruff check src tests scripts

typecheck: ## Type checking
	$(PY) -m mypy src/caliper

check: lint typecheck test ## Everything CI runs

data-verify: ## Confirm the committed fixtures still match their digests
	$(PY) -m caliper.cli data verify

eval: ## The headline result, replayed from recorded model responses. No API key needed.
	$(PY) -m caliper.cli eval --replay

eval-live: ## The same evaluation against a live provider. Requires a key in .env
	$(PY) -m caliper.cli eval --live

baseline: ## The single-prompt baseline on the same cases
	$(PY) -m caliper.cli eval --replay --arm baseline

report: ## Rebuild the results tables and figures from the last run
	$(PY) -m caliper.cli report

clean: ## Remove build and cache artefacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache dist build **/__pycache__
