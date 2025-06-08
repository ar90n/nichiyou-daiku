# nichiyou-daiku (日曜大工)

[![Quality Assurance](https://github.com/YOUR_USERNAME/nichiyou-daiku/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/nichiyou-daiku/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/YOUR_USERNAME/nichiyou-daiku/branch/main/graph/badge.svg)](https://codecov.io/gh/YOUR_USERNAME/nichiyou-daiku)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

DIY Woodworking CAD Library - A Python library for designing furniture using standard lumber sizes and simple joinery methods.

## Features

- 🪵 Support for standard lumber sizes (1x and 2x materials)
- 🔧 Multiple joinery methods (wood screws, dowels, hardware)
- 📐 3D modeling with build123d
- 📋 Automatic assembly instruction generation
- 🔍 Graph-based joint representation

## Installation

```bash
pip install nichiyou-daiku
```

## Quick Start

```python
from nichiyou_daiku.core.lumber import LumberPiece, LumberType

# Create a 2x4 piece, 1000mm long
piece = LumberPiece("leg1", LumberType.LUMBER_2X, 1000)
dimensions = piece.get_dimensions()  # (38.0, 89.0, 1000.0)
```

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/nichiyou-daiku.git
cd nichiyou-daiku

# Install with uv
uv sync --dev
```

### Running Tests

```bash
# Run tests with coverage
make test

# Run all quality checks
make lint

# Format code
make format
```

### Quality Assurance

This project uses Dagger for CI/CD pipelines. The Quality Assurance pipeline includes:

- ✅ **Testing**: pytest with 90% minimum coverage + docstring tests
- 🎨 **Code Formatting**: black code formatter
- 🔍 **Linting**: ruff static analysis
- 🏷️ **Type Checking**: mypy type verification
- 📦 **Building**: Python package distribution

#### Running QA Locally

```bash
# Quick QA run (Python 3.11 only)
make ci-local

# Full QA run (all Python versions)
make ci-all
```

#### GitHub Actions

The Quality Assurance pipeline automatically runs on:
- Push to main branch
- Pull requests
- Manual workflow dispatch

See the [ci/](ci/) directory for pipeline implementation details.

## Project Structure

```
nichiyou-daiku/
├── src/
│   └── nichiyou_daiku/
│       ├── core/           # Core data models
│       ├── connectors/     # Joinery implementations
│       ├── rendering/      # 3D visualization
│       ├── assembly/       # Instruction generation
│       └── utils/          # Utilities
├── tests/                  # Test suite
├── ci/                     # CI/CD pipeline (Dagger)
└── docs/                   # Documentation
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests first (TDD approach)
4. Implement your feature
5. Run `make lint` and fix any issues
6. Submit a pull request

## License

MIT License - see LICENSE file for details