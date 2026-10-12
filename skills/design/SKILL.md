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

Create `<name>.nd`. Name the overall sizes as variables and derive lengths and offsets from them; leave a length unknown (`=?`) where the pieces at both ends fix it. Put the overall size in a comment at the top and group the pieces by section.

## 4. Check and fix

Run `nichiyou-daiku validate <name>.nd`. Fix every error and warning it reports and run it again, until the model is valid. The messages name the piece or connection and say how to fix it. If the same problem survives three attempts, stop and explain it to the user with what you tried.

## 5. Compare with the request

Run `nichiyou-daiku report <name>.nd`. Check the overall size against the request, and read the bill of materials and the shopping list. If the size is off, fix the lengths or offsets and go back to step 4.

## 6. Output files on request

- Drawing: `nichiyou-daiku drawing <name>.nd -o <name>.pdf`
- 3D model: `nichiyou-daiku export <name>.nd -f step` (or `-f stl`)

The first run of these installs build123d and can take a few minutes; tell the user.

## 7. Report

Tell the user the file path, the overall size, the lumber to buy (from the shopping list) and any warning left, with its reason.

## The CLI

`nichiyou-daiku` runs an installed nichiyou-daiku if there is one, otherwise this plugin's own copy through uv. If it says it found neither, ask the user to install uv.
