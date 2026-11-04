.PHONY: help check test lint format rust-check wasm-bindgen-cli wasm web-node-modules web web-dev web-check ci-local ci-setup clean eval eval-full

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

check: lint test rust-check web-check  ## Lint and test; run before every commit (~3min)

test:  ## Run tests with coverage (including doctests)
	uv run pytest src/ tests/ evals/tests --doctest-modules --cov=nichiyou_daiku --cov-report=term-missing -v

lint:  ## Run linting checks
	uv run ruff format --check src/ tests/ evals/ tools/
	uv run ruff check src/ tests/ evals/ tools/
	uv run pyright src/nichiyou_daiku evals

rust-check:  ## Rust: format, lint, test, and build the core for WebAssembly
	cargo fmt --all --check
	cargo clippy --all-targets -- -D warnings
	cargo test
	cargo build -p nichiyou-daiku-core --target wasm32-unknown-unknown

WASM_BINDGEN_VERSION := 0.2.130
WASM := target/wasm32-unknown-unknown/release/nichiyou_daiku_wasm.wasm

wasm-bindgen-cli:  ## Install wasm-bindgen's CLI at the version the crate uses
	@wasm-bindgen --version 2>/dev/null | grep -q "$(WASM_BINDGEN_VERSION)" || \
		cargo install wasm-bindgen-cli --version $(WASM_BINDGEN_VERSION) --locked

wasm: wasm-bindgen-cli  ## Build the core as WebAssembly for the viewer (web/src/wasm)
	cargo build -p nichiyou-daiku-wasm --target wasm32-unknown-unknown --release
	wasm-bindgen --target web --out-dir web/src/wasm $(WASM)
	@ls -l web/src/wasm/nichiyou_daiku_wasm_bg.wasm

web-node-modules:
	@cd web && ([ -d node_modules ] || npm ci --no-audit --no-fund)

web: wasm web-node-modules  ## Build the viewer into web/dist
	cd web && npm run build

web-dev: wasm web-node-modules  ## Open the viewer on a local server
	cd web && npm run dev

web-check: wasm web-node-modules  ## Viewer: type check, tests, build
	cd web && npm run typecheck && npm test && npm run build

format:  ## Format code
	uv run ruff format src/ tests/ evals/ tools/
	cargo fmt --all

# The LLM that designs: sonnet, opus or haiku through Claude Code, deepseek,
# glm or an opencode-go/... name through opencode (the OpenCode Go subscription)
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