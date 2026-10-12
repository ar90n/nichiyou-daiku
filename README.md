# nichiyou-daiku (日曜大工)

[![Quality Assurance](https://github.com/ar90n/nichiyou-daiku/actions/workflows/ci.yml/badge.svg)](https://github.com/ar90n/nichiyou-daiku/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/ar90n/nichiyou-daiku/branch/main/graph/badge.svg)](https://codecov.io/gh/ar90n/nichiyou-daiku)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
![Built with vibe coding](https://img.shields.io/badge/built%20with-vibe%20coding-ff69b4)

A domain-specific CAD system for DIY woodworking, built on the [MO-CAD (Manufacturing Oriented CAD)](https://caddi.tech/archives/4104) concept. Design furniture using a simple DSL that represents real-world construction techniques with standard lumber sizes.

Following the "Worse Is Better" philosophy, nichiyou-daiku prioritizes practical usability over theoretical perfection, making it easy to design and build furniture that can actually be constructed with common tools and materials.

## Quick Example

A corner joint of two 2x4s, written in the DSL:

```nd
(corner_piece_a:2x4 =400)
(corner_piece_b:2x4 =400)

corner_piece_a -[TF<0 BD<0]- corner_piece_b
```

```bash
nichiyou-daiku validate corner.nd           # syntax, placement, overlaps, fasteners
nichiyou-daiku report corner.nd -o report.md # bill of materials, shopping list, cut list
nichiyou-daiku export corner.nd -f step      # 3D model (needs the viz extra)
nichiyou-daiku drawing corner.nd             # technical drawing PDF (needs the viz extra)
```

See [`examples/nd_files/`](examples/nd_files/) for complete designs, such as a table written with variables ([`simple_table_parametric.nd`](examples/nd_files/simple_table_parametric.nd)) and one whose apron length is solved from the legs ([`simple_table_unknowns.nd`](examples/nd_files/simple_table_unknowns.nd)).

## Features

- 📝 A small DSL for furniture: pieces, connections, variables and arithmetic
- 🧩 Unknown lengths (`=?`) and sliding connections (`?` offsets) solved from the other connections
- 📐 Exact placement from all connections at once; contradictions and overlaps are reported
- 🔩 Dowels and screws laid out in the contact area, with preset sizes
- 📑 Markdown reports: bill of materials, shopping list, cut list with saw kerf
- 🎯 STL/STEP export and technical drawings with build123d (optional)
- 🪵 Standard lumber: 1x4, 1x6, 1x8, 2x2, 2x4, 2x6
- 🐍 Typed Python API

## Use with Claude Code

Add this repository as a plugin marketplace and install the plugin:

```text
/plugin marketplace add ar90n/nichiyou-daiku
/plugin install nichiyou-daiku@nichiyou-daiku
```

Then ask for furniture, e.g. "Design a 500 x 400 x 600 side table from 2x4". The `nichiyou-daiku:design` skill writes the `.nd` file, checks it with the CLI until it is sound and reports the size and the lumber to buy. The plugin runs an installed CLI if there is one, otherwise its own copy through [uv](https://docs.astral.sh/uv/).

## Installation

nichiyou-daiku is not on PyPI. Install the CLI from GitHub with uv:

```bash
uv tool install "git+https://github.com/ar90n/nichiyou-daiku"                       # core and CLI
uv tool install "nichiyou-daiku[viz] @ git+https://github.com/ar90n/nichiyou-daiku"  # plus 3D export and drawings (build123d)
```

Run the command again with `--force` to update. The Claude Code plugin follows this repository, so keep an installed CLI up to date with it.

> **Note** build123d currently has limited support for ARM64/aarch64. The core works everywhere.

## Documentation

- [DSL specification](docs/dsl-specification.md): pieces, faces and offsets, connections, variables, unknowns, fasteners, CLI, grammar, errors
- [Python API](docs/api-specification.md): pieces, connections, models, assembly, placement, reports, 3D export
- [Design skill](skills/design/SKILL.md): the Claude Code skill that designs furniture and checks it with the CLI

## Development

```bash
git clone https://github.com/ar90n/nichiyou-daiku.git
cd nichiyou-daiku
uv sync --dev --all-extras

make check     # lint and tests; run before every commit (~30s)
make ci-local  # the full CI pipeline in Dagger; run before merging into main or pushing
make format
```

Design decisions are recorded in [`docs/superpowers/specs/`](docs/superpowers/specs/).

## Contributing

1. Fork the repository and create a feature branch
2. Write tests first (TDD), then implement
3. Run `make check`
4. Open a pull request titled `<type>: <description>`, where type is one of `feat`, `fix`, `docs`, `refactor`, `style`, `chore` or `test`; release notes are grouped by it

## License

Apache 2.0 License - see LICENSE file for details
