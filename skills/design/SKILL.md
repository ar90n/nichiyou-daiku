---
name: design
description: Design DIY furniture from standard 1x/2x SPF lumber (1x4, 2x4, 2x2, ...) as a nichiyou-daiku .nd file, then check and fix it with the nichiyou-daiku CLI. Use when the user wants to design, size or change a table, shelf, bench, rack or other furniture built from 2x4/1x4 lumber, or works on a .nd file.
---

# Design furniture with nichiyou-daiku

Write the furniture as a `.nd` file (the nichiyou-daiku DSL), check it with the `nichiyou-daiku` CLI and fix it until it is sound. Work in the user's project directory.

## 1. Settle the requirements

Check the request against [requirements.md](requirements.md). Ask only for what is missing and changes the design: the overall width × depth × height, the lumber and the joints. Where the user doesn't care, choose (a 2x4 frame, `8x30` dowels for the frame, screws for boards) and say what you chose.

## 2. Read

- The DSL specification: `${CLAUDE_PLUGIN_ROOT}/docs/dsl-specification.md`. Every rule in it applies: faces and offsets, placement, variables, unknowns, fasteners.
- [patterns.md](patterns.md): verified joints and layouts, length formulas, naming and a checklist.
- [examples/](examples/): requirements with a matching `.nd` (a side table, a two-tier shelf, a corner joint). Start from the closest one.

## 3. Write

Create `<name>.nd`. Name the overall sizes as variables and derive lengths and offsets from them; leave a length unknown (`=?`) where the pieces at both ends fix it. Put the overall size in a comment at the top and group the pieces by section. For furniture of more than a few pieces, end with a `steps` block in the order a person would build it: frames first (each frame a step), then the pieces that join them, shelves, and the top last.

## 4. Check and fix

Run `nichiyou-daiku validate --json <name>.nd`. Fix the `error` or every entry in `problems`, and run it again until `valid` is true. If the same problem survives three attempts, stop and explain it to the user with what you tried.

Read the JSON instead of guessing where pieces went (the DSL specification describes every field under "Validation"):

- `pieces[].min` and `max`: each piece's box in mm, with the origin at the smallest corner of the whole model. A piece that sticks out is the one whose box passes the others.
- `pieces[].faces`: the world direction of the piece's `top`, `right` and `front` faces (`down`, `left` and `back` point the other way), so you can tell which face to name in a connection.
- `problems[].kind`:
  - `conflict`: the `connection` contradicts earlier ones; `loop` shows the pieces it runs through and `mismatch_mm` how far off it is.
  - `unconnected`: the `groups` that no connection joins.
  - `overlap`: the two `pieces` share volume.
  - `fastener`: no room for the fastener in the contact area.
  - `hole_collision`: `holes` shows where both holes enter the `piece` and which way they run. Move one connection's offset by more than the hole diameter, or use a shorter fastener.

## 5. Compare with the request

Check `overall_size` in the same JSON against the request (it is null while some pieces are not connected). Its x, y and z run along the width, thickness and length of `size_reference`, the first piece you declared; declare a leg first and z is the height. If it is off, find the piece that sets it in `pieces`, fix its length or offset and go back to step 4. Once the model is valid and the right size, run `nichiyou-daiku report <name>.nd --no-cut-diagram --no-anchor-details --no-pilot-holes` for the bill of materials and the shopping list. If the user tells you the board lengths their store sells (or a saw kerf), write them to `stock.toml` (the format is in the DSL specification under "Report Generation") and add `--stock stock.toml`.

## 6. Look at it

Run `nichiyou-daiku render <name>.nd -o <name>.png` and read the PNG. It shows the model from +z, -y, +x and +x +y +z (the axes of `validate --json`), with each piece's ID where you can see it; pieces hidden in every view are listed in the note at the bottom. Compare it with the request: which way the boards run, the heights of shelves and aprons, which way the legs face, and that nothing floats or sticks out. If something is off, fix it and go back to step 4. The first run installs build123d and can take a few minutes; tell the user.

## 7. Output files on request

- Drawing: `nichiyou-daiku drawing <name>.nd -o <name>.pdf`
- Assembly instructions: `nichiyou-daiku steps <name>.nd` (a `<name>-steps` directory with `steps.md`, a drawing of each drilled part and one image per step); read a few of the images to check the order, the holes and the dimensions
- 3D model: `nichiyou-daiku export <name>.nd -f step` (or `-f stl`)

## 8. Report

Tell the user the file path, the overall size, what to buy from the shopping list (the lumber, the dowels and screws, and the drill bits for their holes) and any warning left, with its reason.

## The CLI

`nichiyou-daiku` runs an installed nichiyou-daiku if there is one, otherwise this plugin's own copy through uv. If it says it found neither, ask the user to install uv.

An installed CLI can be behind this plugin. Ask the user to reinstall it when:

- `render` says `No such command 'render'` or `steps` says `No such command 'steps'` (it predates them): `uv tool install --force "nichiyou-daiku[viz] @ git+https://github.com/ar90n/nichiyou-daiku"`
- `drawing`, `export`, `render` or `steps` says build123d is missing (it lacks the viz extra): `uv tool install --force "nichiyou-daiku[viz] @ git+https://github.com/ar90n/nichiyou-daiku"`
- `validate` says `No such option: --json` (it predates the JSON output): `uv tool install --force "git+https://github.com/ar90n/nichiyou-daiku"`, or the `[viz]` form above
- `validate` rejects syntax that the DSL specification documents (it is older than the plugin): `uv tool install --force "git+https://github.com/ar90n/nichiyou-daiku"`, or the `[viz]` form above

If `render`, `drawing`, `export` or `steps` says the cairo library is missing, ask the user to install it (macOS: `brew install cairo`, Debian/Ubuntu: `sudo apt install libcairo2`).
