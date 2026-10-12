# nichiyou-daiku DSL Specification

The nichiyou-daiku DSL (`.nd` files) is a domain-specific language for concisely describing woodworking furniture designs. Using a Cypher-like syntax, you can define lumber pieces and their connections.

## Table of Contents

- [Basic Structure](#basic-structure)
- [Comments](#comments)
- [Variables and Expressions](#variables-and-expressions)
- [Unknown Lengths and Sliding Connections](#unknown-lengths-and-sliding-connections)
- [Piece Definition](#piece-definition)
- [Connection Definition](#connection-definition)
- [Connection Types](#connection-types)
- [Complete Examples](#complete-examples)
- [CLI Tools](#cli-tools)
- [Grammar (EBNF)](#grammar-ebnf)

## Basic Structure

An `.nd` file consists of the following elements:

1. **Comments** - Lines starting with `//`
2. **Variable Definitions** - Named numbers for lengths and offsets (defined before use)
3. **Piece Definitions** - Lumber piece declarations
4. **Connection Definitions** - Connections between pieces (a piece must be defined before a connection refers to it)

```text
// Comment
(piece_id:piece_type =length)
piece1 -[anchor1 anchor2]- piece2
```

## Comments

Single-line comments start with `//`. End-of-line comments are also supported.

```nd
// This is a comment
(leg:2x4 =720)  // End-of-line comment

// Multiple comment lines
// Project: Dining Table
// Created: 2025-07-30
```

## Variables and Expressions

Name a number with `NAME = expression` and use it wherever a number is expected: lengths, offsets and numeric dowel or screw sizes. Names follow the piece ID rule (letters, digits and underscores, not starting with a digit). A variable must be defined above the line that uses it and cannot be redefined.

```nd
W = 800                        // overall width
GAP = (W - 8 * 89) / 7         // may use earlier variables

(leg:2x4 =720)
(apron:2x4 =W - 2 * 89)        // a length takes any expression
(top:2x4 {"length": 600})

leg -[LB>0 DB>0 D(4, 2 * 15)]- apron   // so do numeric dowel and screw sizes
apron -[RF<GAP BT<0]- top               // compact offset: a number, a variable or (expression)
```

- An expression is built from numbers, variables, `+ - * /`, parentheses and a leading `-`.
- A compact offset takes a number, a variable or a bracketed expression: write `FL<(W / 2)`, not `FL<W / 2`, because the next face letter follows the offset.
- Avoid single face letters (`T`, `D`, `L`, `R`, `F`, `B`) and `V` as names even though they work: `DEPTH` reads better than `D` next to `DF<0`.
- Presets such as `D(:8x30)` and `S(Slim:3.3x25)` are names, not expressions. `Slim` and `Coarse` cannot be the first number of `S(...)`, where they read as screw types; names that only start with them, such as `SlimD`, are fine.
- Variables and piece IDs are separate: variables appear only in expressions, piece IDs only at the ends of a connection.
- An undefined variable (including one defined further down) or a redefinition is a semantic error, and dividing by zero is a validation error. A value that makes no sense, such as a length of 0, is caught by the usual validation.

`examples/nd_files/simple_table_parametric.nd` writes the simple table from its overall size.

## Unknown Lengths and Sliding Connections

Write `?` instead of a number when the connections should decide it.

```nd
(apron_front:2x4 =?)                            // as long as the legs are apart
apron_back -[RB? BD? D(:8x30)]- table_top_2     // also dowel the board to the back apron
```

- `=?` leaves a piece's length unknown; the connections at its two ends fix it.
- `?` as an offset makes a sliding connection: the pieces touch and their edge-shared faces are flush, but they may slide along the shared edge. Another connection must fix where they sit. This fastens a piece to a second support without working out the offset again. Write `?` on both anchors.
- Unknowns are solved when the file is read; reports, 3D models and drawings show the solved values. A sliding connection's offsets are set where the two edges start to overlap.
- It is an error, pointing at the piece or connection, when a length or position is not fixed by the connections (for example when every path between two legs runs through a piece of unknown length), when a length comes out 0 or negative, or when two sliding pieces do not overlap along their edge.
- `?` is available in compact notation only, not in JSON notation.

`examples/nd_files/simple_table_unknowns.nd` is the simple table with an unknown front apron and the top boards doweled to both aprons.

## Piece Definition

Defines a lumber piece.

### Syntax

```text
(piece_id:piece_type =length)
(piece_id:piece_type {"length": length})
```

### Parameters

| Parameter | Description | Required |
|-----------|-------------|----------|
| `piece_id` | Unique identifier for the piece (letters, digits, underscores; must not start with a digit) | Yes (if omitted, a UUID is generated and the piece cannot be referenced) |
| `piece_type` | Type of lumber (`1x4`, `1x6`, `1x8`, `2x2`, `2x4`, `2x6`) | Yes |
| `length` | Length in millimeters, greater than 0 | Yes |

### Lumber Types

| Type | Width (mm) | Thickness (mm) | Description |
|------|------------|----------------|-------------|
| `1x4` | 89 | 19 | One-by-four lumber |
| `1x6` | 140 | 19 | One-by-six lumber |
| `1x8` | 184 | 19 | One-by-eight lumber |
| `2x2` | 38 | 38 | Two-by-two lumber (square: all four long faces are the same size) |
| `2x4` | 89 | 38 | Two-by-four lumber |
| `2x6` | 140 | 38 | Two-by-six lumber |

### Examples

```nd
// Compact notation (recommended)
(leg_1:2x4 =720)
(shelf:1x4 =600)

// JSON format (for future extensions)
(leg_2:2x4 {"length": 720})
```

## Connection Definition

Defines a connection between two pieces.

### Piece Frame and Faces

Every piece is a box with its own local frame:

- **X** = width W (the wide side, from the Lumber Types table; 89mm for 2x4)
- **Y** = thickness T (38mm for 2x lumber, 19mm for 1x lumber)
- **Z** = length

```
Cross-section, looking at the top end (top = +Z points at you):

                 front (+Y)
            ┌──────────────────┐
  left (-X) │                  │ right (+X)     thickness T
            └──────────────────┘
                 back (-Y)
            ←─────── W ────────→

top (+Z) / down (-Z): the two END faces (W x T); the length runs along Z
front / back: WIDE faces (W x length)
left / right: NARROW faces (T x length)
```

| Face | Normal | Kind | Size (on a 2x4: W = 89, T = 38) |
|------|--------|------|---------------------------------|
| `top` | +Z | end face at the max end of the length | W x T |
| `down` | -Z | end face at the min end of the length | W x T |
| `front` | +Y | wide face | W x length |
| `back` | -Y | wide face | W x length |
| `right` | +X | narrow face | T x length |
| `left` | -X | narrow face | T x length |

Face names are local to each piece: `top`/`down` are always the two ends of a piece, even when the piece lies horizontally.

### Connection Model

In nichiyou-daiku, **two pieces always connect by sharing an edge**. This is a fundamental constraint that models real-world woodworking joints.

#### Anchor Components

Each connection has two **anchors**, one per piece:

| Component | Description |
|-----------|-------------|
| `contact_face` | The face that touches the other piece |
| `edge_shared_face` | A face adjacent to contact_face; the anchor lies on the edge where the two faces meet |
| `offset` | Position of the anchor point along that edge |

**Valid face combinations**: contact_face and edge_shared_face must be adjacent (not the same face, not opposite faces). For example:
- ✓ `top` + `front` (adjacent faces)
- ✓ `left` + `back` (adjacent faces)
- ✗ `top` + `down` (opposite faces - invalid)
- ✗ `left` + `right` (opposite faces - invalid)
- ✗ `front` + `back` (opposite faces - invalid)

#### Edge Direction and Offset

The edge runs along the axis perpendicular to both faces, which decides what the offset measures:

| Face pair (either order) | Edge runs along | Edge length | FromMin (`<v`) measured from | FromMax (`>v`) measured from |
|--------------------------|-----------------|-------------|------------------------------|------------------------------|
| top/down + front/back | width (X) | W | left side | right side |
| top/down + left/right | thickness (Y) | T | back side | front side |
| front/back + left/right | length (Z) | L | down end | top end |

The offset must not exceed the edge length; for example `TL<50` on a 2x4 is an error because the top/left edge is only 38mm long.

#### Placement Rules

For `base -[base_anchor target_anchor]- target`, the target is placed so that:

1. **Contact**: the two contact faces touch face to face.
2. **Flush**: the two edge_shared faces lie in one plane and face the same way.
3. **Point**: the two anchor points coincide. With `<` on the target, its min end/side (down/left/back) sits on the point; with `>`, its max end/side (top/right/front) does.

#### Worked Example

A 2x4 leg (L=700) standing on the floor (z=0) and a 2x4 apron (L=500):

```nd
(leg:2x4 =700)
(apron:2x4 =500)
leg -[FL<100 DF<0]- apron
```

- `FL<100` (leg): the leg's front face is the contact face; the front/left edge runs along the leg's length; the point is 100mm above the leg's down end.
- `DF<0` (apron): the apron's down end touches the leg's front face, so the apron runs straight out from the leg; the apron's front face is flush with the leg's left face; the apron's left side sits on the point, so its 89mm width hangs below it. The apron occupies z=11..100.
- With `DF>0`, the apron's right side sits on the point: z=100..189.
- With `FL>100`, the point is 100mm below the leg's top (z=600): z=511..600.
- `leg -[RF<100 LF<0]- apron` stands the apron against the leg's right face (front faces flush), from z=100 up to z=600.

### Syntax

```text
base_piece -[base_anchor target_anchor connection_type?]- target_piece
```

Only one connection per base/target pair is allowed, and a piece cannot connect to itself.

### Anchor Notation

An anchor specifies which face of a piece connects and at what position.

#### Compact Notation (Recommended)

```text
XY<offset  or  XY>offset
```

- **X**: Contact face
- **Y**: Edge shared face
- **<offset**: FromMin (offset from the min end of the edge)
- **>offset**: FromMax (offset from the max end of the edge)

#### Face Abbreviations

| Abbrev | Face | Description |
|--------|------|-------------|
| `T` | top | End face at the max end of the length (+Z) |
| `D` | down | End face at the min end of the length (-Z) |
| `L` | left | Narrow face (-X) |
| `R` | right | Narrow face (+X) |
| `F` | front | Wide face (+Y) |
| `B` | back | Wide face (-Y) |

`B` is **back**, not bottom. The bottom end of a piece is `D` (down), so "front face + bottom end" is `FD` or `DF`; `FB`/`BF` is invalid.

#### Offset

| Notation | Meaning | Description |
|----------|---------|-------------|
| `<0` | FromMin(0) | At the min end of the edge (down end / left side / back side) |
| `<100` | FromMin(100) | 100mm from the min end |
| `>0` | FromMax(0) | At the max end of the edge (top end / right side / front side) |
| `>50` | FromMax(50) | 50mm from the max end |

### Examples

```nd
(leg_1:2x4 =720)
(apron_front:2x4 =600)
(apron_left:2x4 =400)

// leg_1's left face, left/back edge at the leg's top (>0);
// apron_front's down end, down/back edge at its right side (>0):
// apron_front runs out of leg_1's left face, flush with the leg top
leg_1 -[LB>0 DB>0]- apron_front

// leg_1's back face, back/right edge 100mm above its down end;
// apron_left's down end, down/back edge at its left side (<0)
leg_1 -[BR<100 DB<0]- apron_left
```

### JSON Format (Advanced Usage)

```nd
(leg:2x4 =700)
(apron:2x4 =500)
leg -[{"contact_face": "front", "edge_shared_face": "left", "offset": FromMin(100)}
      {"contact_face": "down", "edge_shared_face": "front", "offset": FromMin(0)}]- apron
```

## Connection Types

Specifies the type of connection. Defaults to `V` (vanilla) if omitted.

### Vanilla Connection (V)

Default connection with no special reinforcement and no holes.

```nd
(a:2x4 =400)
(b:2x4 =400)
(c:2x4 =400)
a -[TF<0 BD<0]- b        // Implicit Vanilla
a -[FL<200 DF<0 V]- c    // Explicit Vanilla
```

### Dowel Connection (D)

Connection using wooden dowels.

#### Numeric Specification

```text
piece1 -[anchor anchor D(radius, length)]- piece2
```

- `radius`: Dowel radius in mm
- `length`: **Total** dowel length in mm; half of it goes into each piece

#### Preset Specification

```text
piece1 -[anchor anchor D(:DIAMETERxLENGTH)]- piece2
```

Available presets:

| Preset | Diameter (mm) | Length (mm) |
|--------|---------------|-------------|
| `6x25` | 6 | 25 |
| `6x30` | 6 | 30 |
| `8x25` | 8 | 25 |
| `8x30` | 8 | 30 |
| `8x40` | 8 | 40 |
| `10x30` | 10 | 30 |
| `10x40` | 10 | 40 |
| `12x40` | 12 | 40 |

#### Rules

- Half the dowel length must be shorter than each piece's depth along its contact normal, so the hole does not come out on the far face: front/back contact → thickness, left/right → width, top/down → piece length.
- Holes: φ diameter x length/2 in each piece.
- Dowels and screws: the contact area's short side must be at least 2 × the fastener diameter (pieces touching only along an edge have no contact area); otherwise `validate` reports it and no holes are made. Holes of two connections that run into each other inside a piece are reported too.

#### Examples

```nd
(a:2x4 =400)
(b:2x4 =400)
(c:2x4 =400)

// Preset: 8mm diameter, 30mm total length
a -[TF<0 BD<0 D(:8x30)]- b

// Numeric: radius 4mm, total length 30mm (15mm into each piece)
a -[FL<200 DF<0 D(4, 30)]- c
```

### Screw Connection (S)

Connection using screws. The screw is driven through the target into the base.

#### Numeric Specification

```text
piece1 -[anchor anchor S(diameter, length)]- piece2
```

- `diameter`: Screw diameter in mm
- `length`: Screw length in mm

#### Preset Specification

```text
piece1 -[anchor anchor S(Type:DIAMETERxLENGTH)]- piece2
```

**Slim Screws**

| Preset | Diameter (mm) | Length (mm) |
|--------|---------------|-------------|
| `Slim:3.3x25` | 3.3 | 25 |
| `Slim:3.3x30` | 3.3 | 30 |
| `Slim:3.3x35` | 3.3 | 35 |
| `Slim:3.3x40` | 3.3 | 40 |
| `Slim:3.3x45` | 3.3 | 45 |
| `Slim:3.3x50` | 3.3 | 50 |
| `Slim:3.8x55` | 3.8 | 55 |
| `Slim:3.8x60` | 3.8 | 60 |
| `Slim:3.8x65` | 3.8 | 65 |
| `Slim:3.8x70` | 3.8 | 70 |
| `Slim:3.8x75` | 3.8 | 75 |
| `Slim:4.2x90` | 4.2 | 90 |

**Coarse Thread Screws**

| Preset | Diameter (mm) | Length (mm) |
|--------|---------------|-------------|
| `Coarse:3.8x25` | 3.8 | 25 |
| `Coarse:3.8x30` | 3.8 | 30 |
| `Coarse:3.8x35` | 3.8 | 35 |
| `Coarse:3.8x40` | 3.8 | 40 |
| `Coarse:3.8x45` | 3.8 | 45 |
| `Coarse:3.8x50` | 3.8 | 50 |
| `Coarse:3.8x57` | 3.8 | 57 |
| `Coarse:4.2x65` | 4.2 | 65 |
| `Coarse:4.2x75` | 4.2 | 75 |
| `Coarse:4.5x90` | 4.5 | 90 |
| `Coarse:4.5x100` | 4.5 | 100 |
| `Coarse:5.2x120` | 5.2 | 120 |

#### Rules

- The target's contact_face must be `front` or `back` (the screw goes through the target's wide face).
- Screw length must be greater than the target's thickness (38 for 2x lumber, 19 for 1x lumber).
- Screw length must be shorter than the base's depth along its contact normal (front/back → thickness, left/right → width, top/down → piece length) plus the target's thickness, so the tip stays inside the base.
- Holes: a through-hole in the target and a hole (length - target thickness) deep in the base.

#### Examples

```nd
(post:2x4 =600)
(rail:2x4 =400)
(rail_low:2x4 =400)
(cleat:2x4 =400)

// Preset: Slim screw 3.3x50, rail screwed across the post's front face
post -[FL<300 BT<0 S(Slim:3.3x50)]- rail

// Numeric: 3.5mm diameter, 50mm length
post -[FL<100 BT<0 S(3.5, 50)]- rail_low

// Preset: Coarse thread 3.8x57, cleat screwed face to face behind the post
post -[BT<0 FT<0 S(Coarse:3.8x57)]- cleat
```

## Complete Examples

### Corner Joint

```nd
// Corner joint sample: corner_piece_b lies across corner_piece_a's top end
(corner_piece_a:2x4 =400)
(corner_piece_b:2x4 =400)

corner_piece_a -[TF<0 BD<0]- corner_piece_b
```

### Simple Table

Legs show their 89mm side to the front and their 38mm side to the sides. All aprons stand 89mm tall between the legs, flush with the leg tops, so the front/back aprons are W - 2x89 and the side aprons D - 2x38 long.

```nd
// Simple Table Design: 800 (W) x 600 (D) x 758 (H)

// Legs: leg_1 front-left, leg_2 front-right, leg_3 back-left, leg_4 back-right
(leg_1:2x4 =720)
(leg_2:2x4 =720)
(leg_3:2x4 =720)
(leg_4:2x4 =720)

// Aprons: 800 - 2x89 = 622, 600 - 2x38 = 524
(apron_front:2x4 =622)
(apron_back:2x4 =622)
(apron_left:2x4 =524)
(apron_right:2x4 =524)

// Table top boards (2x4, running front to back)
(table_top_1:2x4 =600)
(table_top_2:2x4 =600)

// Leg to front/back apron connections
leg_1 -[LB>0 DB>0]- apron_front
leg_2 -[RF>0 TF>0]- apron_front
leg_3 -[LB>0 DB>0]- apron_back
leg_4 -[RF>0 TF>0]- apron_back

// Side apron connections
leg_1 -[BR>0 DB>0]- apron_left
leg_3 -[FR>0 TB>0]- apron_left
leg_2 -[BL>0 DF>0]- apron_right
leg_4 -[FL>0 TF>0]- apron_right

// Table top connections: the outer boards rest on the leg tops
table_top_1 -[BD<0 TF<0]- leg_1
table_top_2 -[BD<0 TF<0]- leg_2
```

See [`examples/nd_files/simple_table_compact.nd`](../examples/nd_files/simple_table_compact.nd) for a larger example with a full table top (there the side aprons sit 100mm above the floor, `BR<100`), and [`simple_table_parametric.nd`](../examples/nd_files/simple_table_parametric.nd) for the same table derived from its overall size with variables.

### Shelf with Dowel Joints

```nd
// Shelf with dowel connections: 676 (W) x 89 (D) x 800 (H)
(left_side:2x4 =800)
(right_side:2x4 =800)
(shelf:2x4 =600)

// Shelf ends on the sides' wide faces, shelf underside 300mm above the floor
left_side -[BL<300 DL<0 D(:8x30)]- shelf
right_side -[FL<300 TL<0 D(:8x30)]- shelf
```

## CLI Tools

### Validation

Checks the model described by the file.

```bash
nichiyou-daiku validate furniture.nd
```

### Report Generation

```bash
nichiyou-daiku report furniture.nd -o report.md
nichiyou-daiku report furniture.nd --project-name "My Table"
```

### 3D View (requires build123d)

```bash
nichiyou-daiku view furniture.nd
```

### Export (requires build123d)

```bash
# STL format
nichiyou-daiku export furniture.nd -f stl

# STEP format
nichiyou-daiku export furniture.nd -f step -o model.step

# With fillet radius
nichiyou-daiku export furniture.nd -f stl --fillet-radius 10
```

### Technical Drawing (requires build123d)

```bash
nichiyou-daiku drawing furniture.nd -o furniture.pdf
```

## Grammar (EBNF)

```ebnf
start           = statement+
statement       = piece_def | connection_def | var_def

var_def         = CNAME "=" expr
expr            = term (("+" | "-") term)*
term            = factor (("*" | "/") factor)*
factor          = NUMBER | CNAME | "-" factor | "(" expr ")"

piece_def       = "(" CNAME? ":" PIECE_TYPE (piece_props | compact_length) ")"
PIECE_TYPE      = "1x4" | "1x6" | "1x8" | "2x2" | "2x4" | "2x6"
piece_props     = "{" prop_list? "}"
compact_length  = "=" (expr | "?")
prop_list       = prop ("," prop)*
prop            = ESCAPED_STRING ":" value
value           = ESCAPED_STRING | expr | offset_value

connection_def  = piece_ref "-[" connection_body "]-" piece_ref
connection_body = anchor_props anchor_props connection_type_props?
                | compact_anchor compact_anchor compact_connection_type?
piece_ref       = CNAME

anchor_props         = "{" anchor_prop_list? "}"
anchor_prop_list     = anchor_prop ("," anchor_prop)*
anchor_prop          = ESCAPED_STRING ":" (ESCAPED_STRING | offset_value)
offset_value         = "FromMin" "(" expr ")" | "FromMax" "(" expr ")"

connection_type_props = "{" ( '"type": "vanilla"'
                            | '"type": "dowel", "radius": ' expr ', "depth": ' expr
                            | '"type": "screw", "diameter": ' expr ', "length": ' expr ) "}"

compact_anchor       = COMPACT_FACE COMPACT_FACE compact_offset
compact_offset       = ("<" | ">") (NUMBER | CNAME | "(" expr ")") | "?"
COMPACT_FACE         = "T" | "D" | "L" | "R" | "F" | "B"

compact_connection_type = "V" | dowel_compact | screw_compact
dowel_compact           = "D(" (dowel_preset | dowel_numeric) ")"
dowel_preset            = ":" NUMBER "x" NUMBER
dowel_numeric           = expr "," expr
screw_compact           = "S(" (screw_preset | screw_numeric) ")"
screw_preset            = SCREW_TYPE ":" NUMBER "x" NUMBER
screw_numeric           = expr "," expr
SCREW_TYPE              = "Slim" | "Coarse"

COMMENT         = "//" [^\n]*     (ignored)
```

In the JSON dowel type, `depth` is the total dowel length, as in `D(radius, length)`.

## Error Messages

Errors report the line and column of the offending statement.

### Syntax Errors

```text
DSLSyntaxError: Syntax error at line 1, column 4: Unexpected token '3'. Expected: piece type (1x4, 1x6, 1x8, 2x2, 2x4, 2x6)
```

### Semantic Errors

```text
DSLSemanticError: Unknown piece reference: unknown_piece
DSLSemanticError: Duplicate piece ID: leg_1
DSLSemanticError: Duplicate connection between 'a' and 'b': only one connection per piece pair is supported
DSLSemanticError: Undefined variable 'W' (define it before it is used)
DSLSemanticError: Variable 'W' is already defined
```

### Validation Errors

```text
DSLValidationError: Division by zero
DSLValidationError: The length of 'apron_front' is not fixed by its connections
DSLValidationError: 'b' can slide along z: connections with unknown offsets (?) leave its position open
DSLValidationError: contact_face 'front' and edge_shared_face 'back' must be adjacent faces
DSLValidationError: Offset 50.0mm exceeds piece dimension 38.0mm (piece 'a', edge top/left)
DSLValidationError: Unknown dowel preset: 9x99
DSLValidationError: Unknown Slim screw preset: 3.0x100
DSLValidationError: ScrewConnection target contact_face must be 'front' or 'back', got 'down'
DSLValidationError: Screw length 35.0mm does not reach base piece (target thickness: 38.0mm)
DSLValidationError: Dowel depth 20.0mm (half of 40.0mm) would go through the base piece (19.0mm); use a dowel shorter than 38.0mm
```
