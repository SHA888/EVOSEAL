# Makefile for EVOSEAL project

# Variables
PYTHON = python3
PIP = pip3
PYTEST = pytest
COVERAGE = coverage
FLAKE8 = flake8
BLACK = black
ISORT = isort
MYPY = mypy
PYLINT = pylint
PRECOMMIT = pre-commit

# Default target
.DEFAULT_GOAL := help

# Help target
.PHONY: help
help:
	@echo "EVOSEAL Development Tools"
	@echo ""
	@echo "Usage:"
	@echo "  make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  help           Show this help message"
	@echo "  install        Install the package in development mode"
	@echo "  install-dev    Install development dependencies"
	@echo "  install-precommit  Install pre-commit hooks"
	@echo "  test           Run tests"
	@echo "  test-cov       Run tests with coverage"
	@echo "  lint           Run all linters"
	@echo "  format         Format code with black and isort"
	@echo "  check-format   Check code formatting without making changes"
	@echo "  type-check     Run type checking with mypy"
	@echo "  check          Run all checks (format, lint, type-check, test)"
	@echo "  clean          Clean build artifacts"
	@echo "  clean-all      Clean all generated files"

# Installation
.PHONY: install
install:
	$(PIP) install -e .


.PHONY: install-dev
install-dev:
	$(PIP) install -e ".[dev]"

.PHONY: install-precommit
install-precommit:
	$(PRECOMMIT) install
	$(PRECOMMIT) install --hook-type pre-push

# Testing
.PHONY: test
test:
	$(PYTEST) tests/

.PHONY: test-cov
test-cov:
	$(PYTEST) --cov=evoseal --cov-report=term-missing --cov-report=xml tests/

# Linting and Formatting
.PHONY: lint
lint:
	$(FLAKE8 evoseal tests/
	$(PYLINT) evoseal/

.PHONY: format
format:
	$(BLACK) .
	$(ISORT) .

.PHONY: check-format
check-format:
	$(BLACK) --check .
	$(ISORT) --check-only .

.PHONY: type-check
type-check:
	$(MYPY) evoseal/

# Combined checks
.PHONY: check
check: check-format lint type-check test

# Cleanup
.PHONY: clean
clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .coverage htmlcov/
	find . -type d -name '__pycache__' -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete
	find . -type f -name '*~' -delete

.PHONY: clean-all
clean-all: clean
	rm -rf .venv/ venv/ env/ .eggs/ .mypy_cache/ .pylint.d/ .ruff_cache/
	find . -type d -name '*.egg-info' -exec rm -rf {} +

# Documentation
.PHONY: docs
docs:
	$(MAKE) -C docs html

# Run pre-commit on all files
.PHONY: precommit-all
precommit-all:
	$(PRECOMMIT) run --all-files

# Show dependency tree
.PHONY: deps
deps:
	$(PIP)deptree

# Show outdated packages
.PHONY: outdated
outdated:
	$(PIP) list --outdated

# Update all dependencies
.PHONY: update-deps
update-deps:
	$(PIP) list --outdated --format=freeze | grep -v '^\-e' | cut -d = -f 1 | xargs -n1 $(PIP) install -U

# Run Jupyter notebook
.PHONY: notebook
notebook:
	jupyter notebook

# Run Jupyter lab
.PHONY: lab
lab:
	jupyter lab
