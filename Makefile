.PHONY: help check test lint format ci-local ci-setup clean eval eval-full

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

check: lint test  ## Lint and test; run before every commit (~30s)

test:  ## Run tests with coverage (including doctests)
	uv run pytest src/ tests/ --doctest-modules --cov=nichiyou_daiku --cov-report=term-missing --cov-fail-under=90 -v

lint:  ## Run linting checks
	uv run ruff format --check src/ tests/ evals/
	uv run ruff check src/ tests/ evals/
	uv run pyright src/nichiyou_daiku evals

format:  ## Format code with black
	uv run ruff format src/ tests/ evals/

# The LLM that designs: sonnet, opus or haiku through Claude Code, deepseek or
# glm (free) or an opencode/... name through opencode
MODEL ?= sonnet

eval:  ## Check the design skill on the 5 core requests once, ~15 min (MODEL=sonnet; uses your Claude allowance)
	uv run python -m evals.design.run --cases core --reps 1 --model $(MODEL)

eval-full:  ## Measure the design skill on all 10 requests 3 times, before merging skill changes (MODEL=sonnet; uses your Claude allowance)
	uv run python -m evals.design.run --cases all --reps 3 --model $(MODEL)

ci-setup:  ## Install CI dependencies for local CI runs
	uv sync --group ci --group dev --all-extras

ci-local:  ## Run the full CI pipeline in Dagger; run before merging to main or pushing
	uv run python ci/dagger_pipeline.py

clean:  ## Clean build artifacts
	rm -rf dist/ build/ *.egg-info
	rm -rf .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete