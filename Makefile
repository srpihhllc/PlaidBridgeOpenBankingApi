# /home/srpihhllc/PlaidBridgeOpenBankingApi/Makefile

# Use bash for better scripting
SHELL := /bin/bash

# Default target
.DEFAULT_GOAL := help

# Virtualenv path (match your current venv folder)
VENV := venv

# Lockfiles
RUNTIME_LOCK := requirements.lock
DEV_LOCK := requirements-dev.lock

.PHONY: help sync update test clean migrate rollback lint typecheck dev initdb seed check ci format doctor

help: ## Show available make targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf " make %-12s %s\n", $$1, $$2}'

sync: ## Sync venv to lockfiles
	$(VENV)/bin/pip-sync $(RUNTIME_LOCK) $(DEV_LOCK)

update: ## Recompile lockfiles and sync
	$(VENV)/bin/pip install -U pip-tools
	$(VENV)/bin/pip-compile requirements.txt --output-file=$(RUNTIME_LOCK)
	$(VENV)/bin/pip-compile requirements-dev.txt --output-file=$(DEV_LOCK)
	$(MAKE) sync

test: ## Run pytest with coverage
	$(VENV)/bin/pytest --cov=app --cov-report=term-missing

migrate: ## Apply latest Alembic migrations
	$(VENV)/bin/alembic upgrade head

rollback: ## Downgrade one Alembic migration
	$(VENV)/bin/alembic downgrade -1

initdb: ## Drop, recreate, and migrate the database
	@echo "Dropping and recreating database..."
	$(VENV)/bin/alembic downgrade base
	$(VENV)/bin/alembic upgrade head
	@echo "Database initialized."

seed: ## Populate DB with sample data
	@echo "Seeding database with sample data..."
	$(VENV)/bin/python scripts/seed.py
	@echo "Database seeded."

lint: ## Run flake8 linting
	$(VENV)/bin/flake8 app

typecheck: ## Run mypy type checks
	$(VENV)/bin/mypy app

check: ## Run lint, typecheck, and tests (full suite)
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) test

ci: ## Run full CI suite locally (lint, typecheck, tests, coverage XML)
	$(MAKE) lint
	$(MAKE) typecheck | tee mypy-report.txt
	$(VENV)/bin/pytest --cov=app --cov-report=xml --cov-report=term-missing --maxfail=1 --disable-warnings -q

format: ## Auto-format code with black and isort
	$(VENV)/bin/black app
	$(VENV)/bin/isort app

doctor: ## Check environment health
	@echo "Python: $$(python --version)"
	@echo "Virtualenv: $(VENV)"
	@test -f $(RUNTIME_LOCK) || (echo "Missing $(RUNTIME_LOCK)" && exit 1)
	@test -f $(DEV_LOCK) || (echo "Missing $(DEV_LOCK)" && exit 1)
	@echo "Environment looks good ✅"

dev: ## Run Flask app locally
	FLASK_APP=app FLASK_ENV=development $(VENV)/bin/flask run

clean: ## Remove venv and caches
	rm -rf $(VENV) __pycache__ .pytest_cache .mypy_cache .coverage

# /home/srpihhllc/PlaidBridgeOpenBankingApi/Makefile

# Use bash for better scripting
SHELL := /bin/bash

# Default target
.DEFAULT_GOAL := help

# Virtualenv path (match your current venv folder)
VENV := venv

# Lockfiles
RUNTIME_LOCK := requirements.lock
DEV_LOCK := requirements-dev.lock

.PHONY: help sync update test clean migrate rollback lint typecheck dev initdb seed check ci format doctor

help: ## Show available make targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf " make %-12s %s\n", $$1, $$2}'

sync: ## Sync venv to lockfiles
	$(VENV)/bin/pip-sync $(RUNTIME_LOCK) $(DEV_LOCK)

update: ## Recompile lockfiles and sync
	$(VENV)/bin/pip install -U pip-tools
	$(VENV)/bin/pip-compile requirements.txt --output-file=$(RUNTIME_LOCK)
	$(VENV)/bin/pip-compile requirements-dev.txt --output-file=$(DEV_LOCK)
	$(MAKE) sync

test: ## Run pytest with coverage
	$(VENV)/bin/pytest --cov=app --cov-report=term-missing

migrate: ## Apply latest Alembic migrations
	$(VENV)/bin/alembic upgrade head

rollback: ## Downgrade one Alembic migration
	$(VENV)/bin/alembic downgrade -1

initdb: ## Drop, recreate, and migrate the database
	@echo "Dropping and recreating database..."
	$(VENV)/bin/alembic downgrade base
	$(VENV)/bin/alembic upgrade head
	@echo "Database initialized."

seed: ## Populate DB with sample data
	@echo "Seeding database with sample data..."
	$(VENV)/bin/python scripts/seed.py
	@echo "Database seeded."

lint: ## Run flake8 linting
	$(VENV)/bin/flake8 app

typecheck: ## Run mypy type checks
	$(VENV)/bin/mypy app

check: ## Run lint, typecheck, and tests (full suite)
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) test

ci: ## Run full CI suite locally (lint, typecheck, tests, coverage XML)
	$(MAKE) lint
	$(MAKE) typecheck | tee mypy-report.txt
	$(VENV)/bin/pytest --cov=app --cov-report=xml --cov-report=term-missing --maxfail=1 --disable-warnings -q

format: ## Auto-format code with black and isort
	$(VENV)/bin/black app
	$(VENV)/bin/isort app

doctor: ## Check environment health
	@echo "Python: $$(python --version)"
	@echo "Virtualenv: $(VENV)"
	@test -f $(RUNTIME_LOCK) || (echo "Missing $(RUNTIME_LOCK)" && exit 1)
	@test -f $(DEV_LOCK) || (echo "Missing $(DEV_LOCK)" && exit 1)
	@echo "Environment looks good ✅"

dev: ## Run Flask app locally
	FLASK_APP=app FLASK_ENV=development $(VENV)/bin/flask run

clean: ## Remove venv and caches
	rm -rf $(VENV) __pycache__ .pytest_cache .mypy_cache .coverage




