# Makefile — the dev entry point for jobradar tasks.
# It drives development on the working machine: `make check` = exactly what CI
# runs before every PR.

PY := .venv/bin/python
VENV := .venv

.DEFAULT_GOAL := help

.PHONY: help
help: ## show this list
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

$(VENV): requirements-dev.txt
	python3 -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements-dev.txt
	@touch $(VENV)

.PHONY: install
install: $(VENV) ## create the venv and install dev dependencies

.PHONY: format
format: ## format the code (ruff)
	$(PY) -m ruff format .

.PHONY: lint
lint: ## lint without fixing (ruff)
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

.PHONY: css
css: ## compile SCSS → static/app.css
	$(PY) -c "import sass; open('jobradar/static/app.css','w').write(sass.compile(filename='jobradar/static/app.scss', output_style='expanded'))"

.PHONY: css-check
css-check: ## check that app.css matches app.scss
	$(PY) -c "import sass,sys; sys.exit(0 if open('jobradar/static/app.css').read()==sass.compile(filename='jobradar/static/app.scss', output_style='expanded') else 'app.css is stale — run make css')"

.PHONY: typecheck
typecheck: ## type check (mypy)
	$(PY) -m mypy

.PHONY: test
test: ## pytest
	$(PY) -m pytest

.PHONY: cover
cover: ## pytest under coverage with a report
	$(PY) -m coverage run -m pytest
	$(PY) -m coverage report

.PHONY: check
check: lint typecheck css-check test ## everything CI requires before a commit

.PHONY: run
run: ## one-off radar run (dry-run, no sending)
	$(PY) -m jobradar run --dry-run

.PHONY: serve
serve: ## start the web UI on localhost:8787
	$(PY) -m jobradar serve

.PHONY: clean
clean: ## remove caches and artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -name __pycache__ -type d -not -path './.venv/*' -prune -exec rm -rf {} +
