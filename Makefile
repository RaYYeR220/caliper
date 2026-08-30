# Every target here is also reachable through the `caliper` CLI, so a reviewer on Windows or
# without make can run the same things. See REPRODUCE.md.

PY := .venv/bin/python
ifeq ($(OS),Windows_NT)
PY := .venv/Scripts/python.exe
endif

.DEFAULT_GOAL := help
.PHONY: help install test lint typecheck check data-verify eval eval-record baseline charts report clean

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
	$(PY) -m caliper.cli eval --replay --key eval/answer_key.v1.json --out eval/results-v1

eval-record: ## The same evaluation against a live provider, re-recording the tape. Needs a key.
	$(PY) -m caliper.cli eval --record

baseline: ## The single-prompt baseline on the same cases
	$(PY) -m caliper.cli eval --replay --arms single_prompt

charts: ## Regenerate eval/charts/, the chart summaries the annotators labelled from
	$(PY) scripts/summarise_patients.py

report: ## Rebuild the results tables and figures from the last run, under both answer keys
	$(PY) -m caliper.cli report --compare eval/results-v1 --compare-label "version one of the key"

clean: ## Remove build and cache artefacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache dist build **/__pycache__
