.PHONY: help check test lint format ci-local ci-setup clean

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

check: lint test  ## Lint and test; run before every commit (~30s)

test:  ## Run tests with coverage (including doctests)
	uv run pytest src/ tests/ --doctest-modules --cov=nichiyou_daiku --cov-report=term-missing --cov-fail-under=90 -v

lint:  ## Run linting checks
	uv run ruff format --check src/ tests/
	uv run ruff check src/ tests/
	uv run pyright src/nichiyou_daiku

format:  ## Format code with black
	uv run ruff format src/ tests/

ci-setup:  ## Install CI dependencies for local CI runs
	uv sync --group ci --group dev --all-extras

ci-local:  ## Run the full CI pipeline in Dagger; run before merging to main or pushing
	uv run python ci/dagger_pipeline.py

clean:  ## Clean build artifacts
	rm -rf dist/ build/ *.egg-info
	rm -rf .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete