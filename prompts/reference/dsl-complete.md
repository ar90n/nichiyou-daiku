# Complete DSL Specification

Full specification for the nichiyou-daiku DSL (`.nd` files).

## File Structure

An `.nd` file contains:
1. Comments (optional)
2. Piece definitions
3. Connection definitions (pieces must be defined before they are referenced)

```text
// Comments
(piece_id:piece_type =length)
base_piece -[anchor1 anchor2 connection_type?]- target_piece
```

## Comments

```nd
// Single-line comment
(leg:2x4 =720)  // End-of-line comment

// Multi-line comments
// Project: Dining Table
// Author: Your Name
// Date: 2025-01-01
```

## Piece Definition

### Compact Notation (Recommended)

```text
(piece_id:PIECE_TYPE =length)
```

**Parameters:**
- `piece_id`: Unique identifier (letters, digits, underscores; must not start with a digit). It may be omitted (`(:1x4 =800)`), which generates a UUID; such a piece cannot be referenced by connections.
- `PIECE_TYPE`: `1x4` or `2x4`
- `length`: Length in millimeters (integer or decimal, must be > 0)

**Examples:**
```nd
(leg_1:2x4 =720)
(shelf:1x4 =600)
(top_board:2x4 =1200.5)
```

### JSON Notation

```text
(piece_id:PIECE_TYPE {"length": value})
```

**Example:**
```nd
(leg_1:2x4 {"length": 720})
```

### Lumber Dimensions

| Type | Width (mm) | Thickness (mm) |
|------|------------|----------------|
| 1x4 | 89 | 19 |
| 2x4 | 89 | 38 |

## Piece Frame and Faces

Each piece is a box in its own local frame: **X = width (89)**, **Y = thickness (38 or 19)**, **Z = length**.

| Letter | Face | Normal | Kind | Size on a 2x4 |
|--------|------|--------|------|---------------|
| T | top | +Z | end face (max end of the length) | 89 x 38 |
| D | down | -Z | end face (min end of the length) | 89 x 38 |
| F | front | +Y | wide face | 89 x length |
| B | back | -Y | wide face | 89 x length |
| R | right | +X | narrow face | 38 x length |
| L | left | -X | narrow face | 38 x length |

Face names are local: `top`/`down` are always the ends of a piece, even when the piece lies horizontally. `B` is **back**, not bottom; the bottom end is `D`.

## Connection Definition

### Syntax

```text
base_piece -[BASE_ANCHOR TARGET_ANCHOR CONNECTION_TYPE?]- target_piece
```

Rules enforced by the parser:
- Both pieces must already be defined.
- A piece cannot connect to itself.
- Only one connection per base/target pair.

### Anchor Notation

#### Compact Format (Recommended)

```text
XY<offset  or  XY>offset
```

- `X`: contact_face letter - the face that touches the other piece
- `Y`: edge_shared_face letter - an adjacent face; the anchor lies on the edge where X and Y meet
- `<offset`: FromMin - measured from the min end of the edge
- `>offset`: FromMax - measured from the max end of the edge

#### Edge Direction and Offset

The edge runs along the axis perpendicular to both faces:

| Face pair (either order) | Edge runs along | Edge length (2x4 / 1x4) | `<v` from | `>v` from |
|--------------------------|-----------------|-------------------------|-----------|-----------|
| top/down + front/back | width (X) | 89 / 89 | left side | right side |
| top/down + left/right | thickness (Y) | 38 / 19 | back side | front side |
| front/back + left/right | length (Z) | L / L | down end | top end |

The offset must not exceed the edge length (`TL<50` on a 2x4 is an error).

#### Valid Face Combinations

contact_face and edge_shared_face must be adjacent:

| contact_face | Valid edge_shared_face |
|--------------|------------------------|
| top | front, back, left, right |
| down | front, back, left, right |
| left | top, down, front, back |
| right | top, down, front, back |
| front | top, down, left, right |
| back | top, down, left, right |

**Invalid:** the same face twice, or opposite faces: top+down, left+right, front+back (so `FB`/`BF` is always an error).

#### Placement Rules

`base -[BASE_ANCHOR TARGET_ANCHOR]- target` places the target so that:

1. **Contact**: the two contact faces touch face to face.
2. **Flush**: the two edge_shared faces lie in one plane and face the same way.
3. **Point**: the two anchor points coincide. With `<` on the target its min end/side (down/left/back) sits on the point; with `>` its max end/side (top/right/front) does.

Worked example (leg standing on the floor z=0):

```nd
(leg:2x4 =700)
(apron:2x4 =500)
leg -[FL<100 DF<0]- apron
```

The apron's down end sits on the leg's front face and the apron runs away from the leg; the apron's front face is flush with the leg's left face; the point is 100mm above the leg's down end and the apron's left side sits on it, so the apron's 89mm width hangs below: z=11..100. With `DF>0` it occupies z=100..189; with `FL>100` the point is 100mm below the leg's top (z=600).

#### JSON Format

The same connection with full property names:

```nd
(leg:2x4 =700)
(apron:2x4 =500)
leg -[{"contact_face": "front", "edge_shared_face": "left", "offset": FromMin(100)}
      {"contact_face": "down", "edge_shared_face": "front", "offset": FromMin(0)}]- apron
```

### Connection Types

#### Vanilla (Default)

No reinforcement and no holes. Omit the type or use `V`.

```nd
(a:2x4 =400)
(b:2x4 =400)
(c:2x4 =400)
a -[TF<0 BD<0]- b      // Implicit
a -[FL<200 DF<0 V]- c  // Explicit
```

#### Dowel

```nd
(a:2x4 =400)
(b:2x4 =400)
(c:2x4 =400)
a -[TF<0 BD<0 D(:8x30)]- b     // Preset (diameter x length)
a -[FL<200 DF<0 D(4, 30)]- c   // Numeric (radius, total length)
```

**Available presets:** 6x25, 6x30, 8x25, 8x30, 8x40, 10x30, 10x40, 12x40

- The length is the total dowel length; half goes into each piece.
- Half the length must fit in each piece along its contact normal: front/back → thickness, left/right → 89, top/down → piece length.
- Holes: φ diameter x length/2 in each piece.

#### Screw

The screw is driven through the target into the base.

**Constraints:**
- Target's contact_face must be `front` or `back`.
- Length > target thickness (38 for 2x4, 19 for 1x4).
- Length <= base depth along its contact normal (front/back → thickness, left/right → 89, top/down → piece length) + target thickness.

```nd
(post:2x4 =600)
(rail:2x4 =400)
(cleat:2x4 =400)
// Slim preset: rail screwed across the post's front face
post -[FL<300 BT<0 S(Slim:3.3x50)]- rail
// Coarse preset: cleat screwed face to face behind the post, tops flush
post -[BT<0 FT<0 S(Coarse:3.8x57)]- cleat
```

Numeric form `S(diameter, length)`:

```nd
(post:2x4 =600)
(rail:2x4 =400)
post -[FL<300 BT<0 S(3.5, 50)]- rail
```

Holes: a through-hole in the target and (length - target thickness) deep into the base.

**Slim presets:** 3.3x25, 3.3x30, 3.3x35, 3.3x40, 3.3x45, 3.3x50, 3.8x55, 3.8x60, 3.8x65, 3.8x70, 3.8x75, 4.2x90

**Coarse presets:** 3.8x25, 3.8x30, 3.8x35, 3.8x40, 3.8x45, 3.8x50, 3.8x57, 4.2x65, 4.2x75, 4.5x90, 4.5x100, 5.2x120

## Complete Examples

### Corner Joint

```nd
// Simple corner joint: piece_b lies across piece_a's top end
(piece_a:2x4 =400)
(piece_b:2x4 =400)

piece_a -[TF<0 BD<0]- piece_b
```

### Table Frame

Legs show 89mm to the front and 38mm to the sides; all aprons are 89mm tall, between the legs, flush with the leg tops.

```nd
// Table frame: 800 (W) x 500 (D) x 720 (H)

// Legs
(leg_fl:2x4 =720)
(leg_fr:2x4 =720)
(leg_bl:2x4 =720)
(leg_br:2x4 =720)

// Aprons: front/back = 800 - 2x89 = 622, sides = 500 - 2x38 = 424
(apron_front:2x4 =622)
(apron_back:2x4 =622)
(apron_left:2x4 =424)
(apron_right:2x4 =424)

// Leg to front/back apron
leg_fl -[LB>0 DB>0 D(:8x30)]- apron_front
leg_fr -[RF>0 TF>0 D(:8x30)]- apron_front
leg_bl -[LB>0 DB>0 D(:8x30)]- apron_back
leg_br -[RF>0 TF>0 D(:8x30)]- apron_back

// Leg to side apron
leg_fl -[BR>0 DB>0 D(:8x30)]- apron_left
leg_bl -[FR>0 TB>0 D(:8x30)]- apron_left
leg_fr -[BL>0 DF>0 D(:8x30)]- apron_right
leg_br -[FL>0 TF>0 D(:8x30)]- apron_right
```

### Shelf with Screw Joints

```nd
// Two-tier shelf: 676 (600 + 2x38) wide, 89 deep, 800 tall
(side_l:2x4 =800)
(side_r:2x4 =800)
(shelf_bottom:2x4 =600)
(shelf_top:2x4 =600)

// The screw goes through the side (target, back/front face) into the shelf end (base)
// Bottom shelf: underside 100 above the floor
shelf_bottom -[DL<0 BL<100 S(Slim:3.8x65)]- side_l
shelf_bottom -[TL<0 FL<100 S(Slim:3.8x65)]- side_r

// Top shelf: flush with the top of the sides
shelf_top -[DL<0 BL>38 S(Slim:3.8x65)]- side_l
shelf_top -[TL<0 FL>38 S(Slim:3.8x65)]- side_r
```

## EBNF Grammar

```ebnf
start           = statement+
statement       = piece_def | connection_def

piece_def       = "(" CNAME? ":" PIECE_TYPE (piece_props | compact_length) ")"
PIECE_TYPE      = "1x4" | "2x4"
piece_props     = "{" prop_list? "}"
compact_length  = "=" NUMBER
prop_list       = prop ("," prop)*
prop            = ESCAPED_STRING ":" value

connection_def  = piece_ref "-[" connection_body "]-" piece_ref
connection_body = anchor_props anchor_props connection_type_props?
                | compact_anchor compact_anchor compact_connection_type?
piece_ref       = CNAME

anchor_props    = "{" anchor_prop_list? "}"
anchor_prop_list= anchor_prop ("," anchor_prop)*
anchor_prop     = ESCAPED_STRING ":" (ESCAPED_STRING | offset_value)
offset_value    = "FromMin" "(" NUMBER ")" | "FromMax" "(" NUMBER ")"

connection_type_props = "{" ( '"type": "vanilla"'
                            | '"type": "dowel", "radius": ' NUMBER ', "depth": ' NUMBER
                            | '"type": "screw", "diameter": ' NUMBER ', "length": ' NUMBER ) "}"

compact_anchor  = COMPACT_FACE COMPACT_FACE compact_offset
compact_offset  = "<" NUMBER | ">" NUMBER
COMPACT_FACE    = "T" | "D" | "L" | "R" | "F" | "B"

compact_connection_type = "V" | dowel_compact | screw_compact
dowel_compact   = "D(" (dowel_preset | dowel_numeric) ")"
dowel_preset    = ":" NUMBER "x" NUMBER
dowel_numeric   = NUMBER "," NUMBER
screw_compact   = "S(" (screw_preset | screw_numeric) ")"
screw_preset    = SCREW_TYPE ":" NUMBER "x" NUMBER
screw_numeric   = NUMBER "," NUMBER
SCREW_TYPE      = "Slim" | "Coarse"

COMMENT         = "//" [^\n]*     (ignored, like whitespace)
CNAME           = /[a-zA-Z_][a-zA-Z0-9_]*/
NUMBER          = /[0-9]+(\.[0-9]+)?/
```

In the JSON dowel type, `depth` is the total dowel length (same meaning as the second number of `D(radius, length)`).

## Error Messages

| Error Type | Example | Cause |
|------------|---------|-------|
| DSLSyntaxError | "Syntax error at line 1, column 4: Unexpected token '3'. Expected: piece type (1x4, 2x4)" | Invalid syntax, e.g. unknown lumber type `3x4` |
| DSLSemanticError | "Unknown piece reference: foo" | Reference to an undefined piece |
| DSLSemanticError | "Duplicate piece ID: leg_1" | Same ID used twice |
| DSLSemanticError | "Duplicate connection between 'a' and 'b' ..." | Second connection for the same base/target pair |
| DSLValidationError | "contact_face 'front' and edge_shared_face 'back' must be adjacent faces" | Same or opposite faces in an anchor |
| DSLValidationError | "Offset 50.0mm exceeds piece dimension 38.0mm ..." | Offset longer than the anchor's edge |
| DSLValidationError | "Unknown dowel preset: 9x99" | Non-existent preset |
| DSLValidationError | "ScrewConnection target contact_face must be 'front' or 'back' ..." | Screw target contacts with another face |
| DSLValidationError | "Screw length 35.0mm does not reach base piece ..." | Screw not longer than the target thickness |
| DSLValidationError | "Dowel depth 20.0mm (half of 40.0mm) exceeds ..." | Dowel half-length does not fit a piece |

Error messages include the line and column of the offending statement.

## CLI Commands

```bash
# Validate the model
nichiyou-daiku validate furniture.nd

# Generate report
nichiyou-daiku report furniture.nd -o report.md

# 3D view (requires build123d)
nichiyou-daiku view furniture.nd

# Export to STL/STEP (requires build123d)
nichiyou-daiku export furniture.nd -f stl
nichiyou-daiku export furniture.nd -f step -o model.step

# Technical drawing PDF (requires build123d)
nichiyou-daiku drawing furniture.nd -o furniture.pdf
```
