---
name: design
description: Design DIY furniture from standard 1x/2x SPF lumber (1x4, 2x4, 2x2, ...) as a nichiyou-daiku .nd file, then check and fix it with the nichiyou-daiku CLI. Use when the user wants to design, size or change a table, shelf, bench, rack or other furniture built from 2x4/1x4 lumber, or works on a .nd file.
---

# Design furniture with nichiyou-daiku

Write the furniture as a `.nd` file (the nichiyou-daiku DSL), check it with the `nichiyou-daiku` CLI and fix it until it is sound. Work in the user's project directory: it is where you start, and `nichiyou-daiku` is on the PATH, so there is nothing to look around for. This skill, the files it links and the CLI's output are all you need: don't search the plugin's other files or its source code, and make only the files the user asks for (the outputs of step 7 only on request).

## 1. Settle the requirements

Check the request against [requirements.md](requirements.md). Ask only for what is missing and changes the design: the overall width × depth × height, the lumber and the joints. Where the user doesn't care, choose (a 2x4 frame, `8x30` dowels for the frame, screws for boards) and say what you chose.

## 2. Read

Read these together, in one step:

- The DSL specification: [docs/dsl-specification.md](../../docs/dsl-specification.md), in the plugin's root two directories above this skill; its first 487 lines, up to "Complete Examples" (the CLI, grammar and error sections after them are not needed to design). Every rule in it applies: faces and offsets, placement, variables, unknowns, fasteners.
- [patterns.md](patterns.md): verified joints and layouts, length formulas, naming and a checklist.
- The closest of [examples/](examples/), requirements with a matching `.nd` (a side table, a two-tier shelf, a corner joint). Start from it.

## 3. Write

Write every file in the working directory, scratch files too. Create `<name>.nd`. Name the overall sizes as variables and derive lengths and offsets from them; leave a length unknown (`=?`) where the pieces at both ends fix it. Put the overall size in a comment at the top and group the pieces by section. For furniture of more than a few pieces, end with a `steps` block in the order a person would build it: frames first (each frame a step), then the pieces that join them, shelves, and the top last.

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

Check `overall_size` in the same JSON against the request (it is null while some pieces are not connected). Its x, y and z run along the width, thickness and length of `size_reference`, the first piece you declared; declare a leg first and z is the height. The furniture's width must come out along x and its depth along y (the front faces +y): hang the long aprons and rails on the legs' left and right faces, as in patterns.md, and if x and y come out swapped, move them there. If it is off, find the piece that sets it in `pieces`, fix its length or offset and go back to step 4. If the user tells you the board lengths their store sells (or a saw kerf), write them to `stock.toml` (the format is in the DSL specification under "Report Generation") for the report in step 6.

## 6. Look at it

Once the model is valid and the right size, draw it and list the materials in one command, `nichiyou-daiku render <name>.nd -o <name>.png && nichiyou-daiku report <name>.nd --no-cut-diagram --no-anchor-details --no-pilot-holes` (add `--stock stock.toml` if you wrote one), for the bill of materials and the shopping list, then read the PNG. It shows the model from +z, +y, -x and -x +y +z (the axes of `validate --json`): the top, the front (the furniture's front faces +y), the right side and an isometric view, with each piece's ID where you can see it; pieces hidden in every view are listed in the note at the bottom. Compare it with the request: which way the boards run, the heights of shelves and aprons, which way the legs face, and that nothing floats or sticks out. If something is off, fix it and go back to step 4.

## 7. Output files on request

- Drawing: `nichiyou-daiku drawing <name>.nd -o <name>.pdf`
- Assembly instructions: `nichiyou-daiku steps <name>.nd` (a `<name>-steps` directory with `steps.md`, a drawing of each drilled part and one image per step); read a few of the images to check the order, the holes and the dimensions
- 3D model: `nichiyou-daiku export <name>.nd -f step` (or `-f stl`)

## 8. Report

Tell the user the file path, the overall size, what to buy from the shopping list (the lumber, the dowels and screws, and the drill bits for their holes) and any warning left, with its reason.

## The CLI

`nichiyou-daiku` runs this plugin's own version of the CLI, which it downloads the first time (a few seconds; tell the user). If it says it could not download it, tell the user what it said: they can download the CLI by hand from the release it names and put it where it says, or install Rust (https://rustup.rs) so that it builds the CLI from the plugin's source; then run the command again.
