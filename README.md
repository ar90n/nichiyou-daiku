# nichiyou-daiku (日曜大工)

[![CI](https://github.com/YOUR_USERNAME/nichiyou-daiku/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/nichiyou-daiku/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/YOUR_USERNAME/nichiyou-daiku/branch/main/graph/badge.svg)](https://codecov.io/gh/YOUR_USERNAME/nichiyou-daiku)

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

### CI/CD

This project uses Dagger for CI/CD pipelines. The CI runs:
- Tests with pytest and coverage (90% minimum)
- Code formatting with black
- Linting with ruff
- Type checking with mypy
- Package building

#### Running CI Locally

```bash
# Quick CI run (Python 3.11 only)
make ci-local

# Full CI run (all Python versions)
make ci-all
```

#### GitHub Actions

The CI automatically runs on:
- Push to main branch
- Pull requests
- Manual workflow dispatch

## Project Structure

```
nichiyou_daiku/
├── core/           # Core data models
├── connectors/     # Joinery implementations
├── rendering/      # 3D visualization
├── assembly/       # Instruction generation
└── utils/          # Utilities
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