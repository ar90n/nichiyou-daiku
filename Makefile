.PHONY: help test lint format ci-local ci-all clean

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

test:  ## Run tests with coverage
	uv run pytest tests/ --cov=nichiyou_daiku --cov-report=term-missing -v

lint:  ## Run linting checks
	uv run black --check src/ tests/
	uv run ruff check src/ tests/
	uv run mypy src/nichiyou_daiku

format:  ## Format code with black
	uv run black src/ tests/

ci-local:  ## Run CI pipeline locally (Python 3.11 only)
	./run-ci-local.sh

ci-all:  ## Run CI pipeline for all Python versions
	./run-ci-local.sh "3.11,3.12"

clean:  ## Clean build artifacts
	rm -rf dist/ build/ *.egg-info
	rm -rf .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete