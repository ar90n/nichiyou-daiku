# nichiyou-daiku (日曜大工)

[![Quality Assurance](https://github.com/ar90n/nichiyou-daiku/actions/workflows/ci.yml/badge.svg)](https://github.com/ar90n/nichiyou-daiku/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/ar90n/nichiyou-daiku/branch/main/graph/badge.svg)](https://codecov.io/gh/ar90n/nichiyou-daiku)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
![Built with vibe coding](https://img.shields.io/badge/built%20with-vibe%20coding-ff69b4)

A Python library for designing DIY furniture using standard lumber sizes and simple joinery methods. Create 3D models of your woodworking projects with an intuitive API that represents real-world construction techniques.

## Features

- 🪵 Support for standard lumber size (2x4 and 1x4)
- 🔗 Flexible connection system with precise offset control
- 📐 3D visualization with build123d (optional)
- 🧩 Piece-oriented design matching real woodworking
- 📊 Graph-based assembly representation
- 🎯 Type-safe API with full type hints
- 📋 Resource extraction for bill of materials
- 📑 Markdown report generation with cut optimization

## Installation

```bash
# Basic installation
pip install nichiyou-daiku

# With visualization support
pip install "nichiyou-daiku[viz]"

# Development installation with uv
uv pip install -e ".[viz]"
```

> **Note**: The visualization feature requires build123d, which currently has limited support for ARM64/aarch64 platforms. Core functionality works on all platforms.

## Quick Start

```python
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.model import Model, PiecePair
from nichiyou_daiku.core.connection import Connection, BasePosition, Anchor
from nichiyou_daiku.core.geometry import Face, Edge, EdgePoint, FromMin

# Create lumber pieces
horizontal_beam = Piece.of(PieceType.PT_2x4, 800.0, "beam")
vertical_post = Piece.of(PieceType.PT_2x4, 400.0, "post")

# Define how pieces connect
connection = Connection.of(
    base=BasePosition(
        face="front",  # Connect to front face of beam
        offset=FromMin(value=400.0)  # 400mm from edge
    ),
    target=Anchor(
        face="down",  # Bottom of post connects to beam
        edge_point=EdgePoint(
            edge=Edge(lhs="down", rhs="front"),
            offset=FromMin(value=44.5)  # Centered on post
        )
    )
)

# Create a model with connected pieces
model = Model.of(
    pieces=[horizontal_beam, vertical_post],
    connections=[(PiecePair(base=horizontal_beam, target=vertical_post), connection)]
)
```

## Development

### Setup

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Clone the repository
git clone https://github.com/ar90n/nichiyou-daiku.git
cd nichiyou-daiku

# Install development dependencies
uv sync --dev

# Install with visualization support
uv sync --all-extras
```

### Running Tests

```bash
# Run tests with coverage
uv run pytest --cov=nichiyou_daiku --cov-report=term-missing

# Run specific test file
uv run pytest tests/core/test_piece.py -v

# Run with doctest
uv run python -m doctest src/nichiyou_daiku/core/piece.py
```

### Code Quality

```bash
# Format code
uv run ruff format src/ tests/

# Lint code
uv run ruff check src/ tests/

# Type checking
uv run pyright src/

# Run all checks
make lint
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
make ci-local
```

#### GitHub Actions

The Quality Assurance pipeline automatically runs on:
- Push to main branch
- Pull requests
- Manual workflow dispatch

See the [ci/](ci/) directory for pipeline implementation details.

## Examples

Check out the `examples/` directory for complete working examples:

- **`simple_table.py`** - A basic four-legged table demonstrating fundamental connections
- **`basic_joints.py`** - Different joint types (T-joint, butt joint, corner joint)
- **`corner_angle.py`** - Complex corner connections with precise angle control
- **`utils.py`** - Helper functions for creating common structures
- **`resource_demo.py`** - Demonstrates resource extraction and bill of materials
- **`report_demo.py`** - Shows report generation with cut optimization

### Visualizing with build123d

```python
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.shell import assembly_to_build123d
from ocp_vscode import show

# Convert model to 3D assembly
assembly = Assembly.of(model)
compound = assembly_to_build123d(assembly)

# Visualize in OCP CAD Viewer
show(compound)
```

### Resource Extraction

Extract bill of materials from your models to understand lumber requirements:

```python
from nichiyou_daiku.core.resources import extract_resources

# Extract resources from a model
resources = extract_resources(model)

# Get summary information
print(resources.pretty_print())
# Output: piece counts, total lengths by type, volume

# Export as JSON
json_data = resources.model_dump_json(indent=2)

# Access detailed information
for piece_type, count in resources.pieces_by_type.items():
    total_length = resources.total_length_by_type[piece_type]
    print(f"{piece_type.value}: {count} pieces, {total_length}mm total")
```

### Report Generation

Generate comprehensive markdown reports with shopping lists and cut optimization:

```python
from nichiyou_daiku.shell.report_generator import generate_markdown_report

# Generate report with custom standard lengths
custom_lengths = {
    PieceType.PT_2x4: [2400.0, 3000.0, 3600.0],  # metric lengths
    PieceType.PT_1x4: [1800.0, 2400.0, 3000.0],
}

report = generate_markdown_report(
    resources,
    project_name="My Table Project",
    standard_lengths=custom_lengths,
    include_cut_diagram=True
)

# Save report
with open("project_report.md", "w") as f:
    f.write(report)
```

The report includes:
- Project overview with total materials needed
- Detailed bill of materials table
- Shopping list aggregated by lumber type
- Purchase recommendations with optimal board usage
- Cut diagrams showing how to minimize waste

## Project Structure

```
nichiyou-daiku/
├── src/
│   └── nichiyou_daiku/
│       ├── core/           # Core data models
│       │   ├── piece.py    # Lumber piece definitions
│       │   ├── model.py    # Assembly graph model
│       │   ├── connection.py # Connection specifications
│       │   ├── assembly.py # 3D assembly generation
│       │   ├── resources.py # Resource extraction
│       │   └── geometry/   # Geometric primitives
│       │       ├── face.py, edge.py, corner.py
│       │       ├── coordinates.py, dimensions.py
│       │       └── offset.py
│       └── shell/          # External integrations
│           ├── build123d_export.py
│           └── report_generator.py
├── examples/               # Example projects
├── tests/                  # Test suite
└── ci/                     # CI/CD pipeline (Dagger)
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests first (TDD approach)
4. Implement your feature
5. Run quality checks (`make lint` or `uv run ruff check`)
6. Commit your changes (`git commit -m 'feat: Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Pull Request Guidelines

To ensure your contributions are properly categorized in release notes, please follow these PR title conventions:

#### PR Title Format
Your PR title should follow the pattern: `<type>: <description>`

- **feat:** New features or functionality
  - Example: `feat: Add support for 1x4 lumber sizes`
- **fix:** Bug fixes
  - Example: `fix: Correct joint position calculation for angled connections`
- **docs:** Documentation updates
  - Example: `docs: Add assembly guide for complex joints`
- **refactor:** Code restructuring without changing functionality
  - Example: `refactor: Simplify connection validation logic`
- **style:** Code style/formatting changes
  - Example: `style: Apply consistent naming to geometry modules`
- **chore:** Maintenance tasks, dependency updates
  - Example: `chore: Update pydantic to 2.12.0`
- **test:** Test additions or modifications
  - Example: `test: Add edge cases for corner joint creation`

These prefixes are automatically used by our release automation to categorize changes in release notes.

### Development Philosophy

- **Test-Driven Development**: Write tests before implementation
- **Type Safety**: All public APIs must have type hints
- **Immutability**: Prefer frozen dataclasses and pure functions
- **Real-world Modeling**: APIs should match how woodworkers think

## License

Apache 2.0 License - see LICENSE file for details
