# nichiyou-daiku (日曜大工)

[![Quality Assurance](https://github.com/ar90n/nichiyou-daiku/actions/workflows/ci.yml/badge.svg)](https://github.com/ar90n/nichiyou-daiku/actions/workflows/ci.yml)
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
nichiyou-daiku validate corner.nd            # syntax, placement, overlaps, fasteners
nichiyou-daiku report corner.nd -o report.md # bill of materials, shopping list, cut list
nichiyou-daiku view corner.nd                # the 3D model, the steps and the manual in your browser
nichiyou-daiku export corner.nd -f step      # 3D model (STEP or STL)
nichiyou-daiku drawing corner.nd             # technical drawing PDF with dimensions
nichiyou-daiku render corner.nd              # check image PNG, four labelled views
nichiyou-daiku steps corner.nd               # assembly steps: Markdown, part drawings and step images
```

See [`examples/nd_files/`](examples/nd_files/) for complete designs, such as a table written with variables ([`simple_table_parametric.nd`](examples/nd_files/simple_table_parametric.nd)) and one whose apron length is solved from the legs ([`simple_table_unknowns.nd`](examples/nd_files/simple_table_unknowns.nd)).

## Features

- 📝 A small DSL for furniture: pieces, connections, variables and arithmetic
- 🧩 Unknown lengths (`=?`) and sliding connections (`?` offsets) solved from the other connections
- 📐 Exact placement from all connections at once; contradictions and overlaps are reported
- 🔩 Dowels and screws laid out in the contact area, with preset sizes, counterbores and countersinks
- 📑 Markdown reports: bill of materials, shopping list with hardware and drill bits, cut list for your store's board lengths and saw kerf
- 🖼️ Technical drawings, check images and assembly instructions with a drawing of each drilled part
- 🎯 STL and STEP export with every hole
- 🌐 A browser viewer: the 3D model, the assembly steps and a printable manual
- 🪵 Standard lumber: 1x4, 1x6, 1x8, 2x2, 2x4, 2x6
- 📦 One executable for Linux, macOS and Windows

## Use with Claude Code

Add this repository as a plugin marketplace and install the plugin:

```text
/plugin marketplace add ar90n/nichiyou-daiku
/plugin install nichiyou-daiku@nichiyou-daiku
```

Then ask for furniture, e.g. "Design a 500 x 400 x 600 side table from 2x4". The `nichiyou-daiku:design` skill writes the `.nd` file, checks it with the CLI until it is sound and reports the size and the lumber to buy. The plugin downloads its own version of the CLI from this repository's releases the first time (a few seconds).

## Installation

On Linux and macOS (x86_64 or arm64):

```bash
curl -fsSL https://raw.githubusercontent.com/ar90n/nichiyou-daiku/main/install.sh | sh
```

It installs the newest release's CLI into `~/.local/bin`, checked against the release's checksums, and says if that folder is not on your PATH. `--version 0.2.0` installs another version and `--to <folder>` another place (`... | sh -s -- --to ~/bin`). Run it again to update. On Windows, download `nichiyou-daiku-<version>-x86_64-pc-windows-msvc.zip` from the [releases](https://github.com/ar90n/nichiyou-daiku/releases) and put `nichiyou-daiku.exe` on your PATH. `nichiyou-daiku --version` tells which version you have.

If you installed the Python version with uv, remove it: `uv tool uninstall nichiyou-daiku`. It stays available, with its Python API, as v0.1.0: `uv tool install "git+https://github.com/ar90n/nichiyou-daiku@v0.1.0"`.

To build it from source, with Rust and Node.js 24 or later:

```bash
git clone https://github.com/ar90n/nichiyou-daiku.git
cd nichiyou-daiku
make web                                        # the viewer that view serves
cargo install --path crates/nichiyou-daiku-cli
```

## Viewer

`nichiyou-daiku view design.nd` opens the design in your browser, served from your machine: the 3D model with its holes, what `validate` finds and the source beside it. The page follows the file as you save it. Nothing leaves your machine.

The viewer is also a static site: `make web` builds it into `web/dist` (`make web-dev` serves it while you work on it). Open a file with **Open** or by dropping it on the page, or open a URL: `?src=<URL of an .nd>` opens it when the page loads, so the address can be shared. The server must let other sites read the file; on GitHub, use the raw file (`raw.githubusercontent.com`) or a gist's raw URL. The `Viewer on GitHub Pages` workflow publishes the viewer when started by hand (choose "GitHub Actions" as the Pages source first).

The **Steps** tab walks through the assembly: the parts list, then one step at a time (with **◀ Prev** / **Next ▶** or the arrow keys), drawing the part each step leaves with the step's pieces in blue. `?step=N` opens a step (0 is the parts list). The steps come from the design's `steps` block, or one piece at a time without one.

On a step, the 3D shows its dimensions as the CLI's step images do: where the step's pieces go, stopping at both ends of them and of the pieces they join, and the part's overall size. **Dimensions** turns the camera to the view they read best from; the checkbox hides them. Values that would overlap are hidden, lumber sizes first; zoom in to see them.

In the parts list, **Drawing** opens a drilled part's drawing in place of the 3D, as the CLI's part drawings show it: the isometric view with the drilled faces lettered, and each face with its holes dimensioned from the reference end (▲). Zoom with the wheel or two fingers, drag to move; **3D** goes back.

An open step has a **Drawing** too: the step image the CLI writes, the part it leaves seen from the isometric (the step's pieces in black, earlier ones grey) beside the dimension view. With it open, **◀ Prev** / **Next ▶** move to the next step's drawing.

The **Manual** tab lays the whole manual out as A4 landscape pages: what to get (the parts, numbered as their drawings, and every fastener the steps use), each drilled part's drawing, and a page per step with its drawing, pieces and fasteners. **Print** puts just those pages on paper.

## Documentation

- [DSL specification](docs/dsl-specification.md): pieces, faces and offsets, connections, variables, unknowns, fasteners, CLI, grammar, errors
- [Design skill](skills/design/SKILL.md): the Claude Code skill that designs furniture and checks it with the CLI

## Development

```bash
git clone https://github.com/ar90n/nichiyou-daiku.git
cd nichiyou-daiku
uv sync --group dev --group ci   # the Python of the evaluation and CI

make check             # Rust, the viewer and the evaluation; run before every commit
make ci-local          # the full CI pipeline in Dagger; run before merging into main or pushing
make format
ND_BLESS=1 cargo test  # after changing what the CLI prints: rewrite the golden files, then review the diff
```

To release, push a tag `v<version>` with the version in `Cargo.toml`: the Release workflow builds the CLI for five systems into a draft release. Publish it after checking it, and before that version reaches main, since the plugin downloads its own version.

Design decisions are recorded in [`docs/superpowers/specs/`](docs/superpowers/specs/).

## Contributing

1. Fork the repository and create a feature branch
2. Write tests first (TDD), then implement
3. Run `make check`
4. Open a pull request titled `<type>: <description>`, where type is one of `feat`, `fix`, `docs`, `refactor`, `style`, `chore` or `test`

## License

Apache 2.0 License - see LICENSE file for details
