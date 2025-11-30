# Complete DSL Specification

Full specification for the nichiyou-daiku DSL (`.nd` files).

## File Structure

An `.nd` file contains:
1. Comments (optional)
2. Piece definitions
3. Connection definitions

```nd
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

```nd
(piece_id:PIECE_TYPE =length)
```

**Parameters:**
- `piece_id`: Unique identifier (letters, numbers, underscores, must start with letter)
- `PIECE_TYPE`: `1x4` or `2x4`
- `length`: Length in millimeters (integer or decimal)

**Examples:**
```nd
(leg_1:2x4 =720)
(shelf:1x4 =600)
(top_board:2x4 =1200.5)
```

### JSON Notation

```nd
(piece_id:PIECE_TYPE {"length": value})
```

**Example:**
```nd
(leg_1:2x4 {"length": 720})
```

### Lumber Dimensions

| Type | Width (mm) | Height (mm) |
|------|------------|-------------|
| 1x4 | 89 | 19 |
| 2x4 | 89 | 38 |

## Connection Definition

### Syntax

```nd
base_piece -[BASE_ANCHOR TARGET_ANCHOR CONNECTION_TYPE?]- target_piece
```

### Anchor Notation

#### Compact Format (Recommended)

```
XY<offset  or  XY>offset
```

- `X`: contact_face (T/D/L/R/F/B)
- `Y`: edge_shared_face (T/D/L/R/F/B)
- `<offset`: FromMin (measured from start)
- `>offset`: FromMax (measured from end)

#### Face Abbreviations

| Abbrev | Face | Description |
|--------|------|-------------|
| T | top | Upper face (+Z) |
| D | down | Lower face (-Z) |
| L | left | Left side (-Y) |
| R | right | Right side (+Y) |
| F | front | Front end (+X, length end) |
| B | back | Back end (-X, length start) |

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

**Invalid (opposite faces):** top+down, left+right, front+back

#### JSON Format

```nd
piece1 -[{"contact_face": "top", "edge_shared_face": "front", "offset": FromMin(0)}
         {"contact_face": "down", "edge_shared_face": "left", "offset": FromMax(100)}]- piece2
```

### Connection Types

#### Vanilla (Default)

No reinforcement. Omit or use `V`.

```nd
piece1 -[TF<0 BD<0]- piece2      // Implicit
piece1 -[TF<0 BD<0 V]- piece2    // Explicit
```

#### Dowel

```nd
// Preset (diameter x length)
piece1 -[TF<0 BD<0 D(:8x30)]- piece2

// Numeric (radius, depth)
piece1 -[TF<0 BD<0 D(4.0, 15.0)]- piece2
```

**Available presets:** 6x25, 6x30, 8x25, 8x30, 8x40, 10x30, 10x40, 12x40

#### Screw

**Constraint:** Target's contact_face must be `front` or `back`.

```nd
// Slim screw preset (base: back+top, target: front+top)
piece1 -[BT<0 FT<0 S(Slim:3.3x50)]- piece2

// Coarse screw preset
piece1 -[BT<0 FT<0 S(Coarse:3.8x57)]- piece2

// Numeric (diameter, length)
piece1 -[BT<0 FT<0 S(3.5, 50.0)]- piece2
```

**Slim presets:** 3.3x25, 3.3x30, 3.3x35, 3.3x40, 3.3x45, 3.3x50, 3.8x55, 3.8x60, 3.8x65, 3.8x70, 3.8x75, 4.2x90

**Coarse presets:** 3.8x25, 3.8x30, 3.8x35, 3.8x40, 3.8x45, 3.8x50, 3.8x57, 4.2x65, 4.2x75, 4.5x90, 4.5x100, 5.2x120

## Complete Examples

### Corner Joint

```nd
// Simple corner joint
(piece_a:2x4 =400)
(piece_b:2x4 =400)

piece_a -[TF<0 BD<0]- piece_b
```

### Four-Legged Table

```nd
// Four-Legged Table
// Dimensions: 800mm x 500mm x 720mm

// Legs
(leg_fl:2x4 =720)
(leg_fr:2x4 =720)
(leg_bl:2x4 =720)
(leg_br:2x4 =720)

// Aprons (800 - 2*89 = 622mm, 500 - 2*89 = 322mm)
(apron_front:2x4 =622)
(apron_back:2x4 =622)
(apron_left:2x4 =322)
(apron_right:2x4 =322)

// Leg to front/back apron
leg_fl -[LB>0 DB<0 D(:8x30)]- apron_front
leg_fr -[RB>0 DB>0 D(:8x30)]- apron_front
leg_bl -[LB>0 DB<0 D(:8x30)]- apron_back
leg_br -[RB>0 DB>0 D(:8x30)]- apron_back

// Leg to side apron
leg_fl -[FT>0 DB<0 D(:8x30)]- apron_left
leg_bl -[BT>0 DB>0 D(:8x30)]- apron_left
leg_fr -[FT>0 DB<0 D(:8x30)]- apron_right
leg_br -[BT>0 DB>0 D(:8x30)]- apron_right
```

### Shelf with Screw Joints

```nd
// Two-tier shelf with screw connections
(side_l:2x4 =800)
(side_r:2x4 =800)
(shelf_bottom:2x4 =600)
(shelf_top:2x4 =600)

// Bottom shelf (target contact_face must be front or back for screws)
side_l -[RT<50 FT<0 S(Slim:3.8x65)]- shelf_bottom
side_r -[LT<50 FT>0 S(Slim:3.8x65)]- shelf_bottom

// Top shelf
side_l -[RT>50 FT<0 S(Slim:3.8x65)]- shelf_top
side_r -[LT>50 FT>0 S(Slim:3.8x65)]- shelf_top
```

## EBNF Grammar

```ebnf
start           = statement+
statement       = piece_def | connection_def | COMMENT

piece_def       = "(" CNAME ":" PIECE_TYPE (piece_props | compact_length) ")"
PIECE_TYPE      = "1x4" | "2x4"
piece_props     = "{" prop_list? "}"
compact_length  = "=" NUMBER
prop_list       = prop ("," prop)*
prop            = ESCAPED_STRING ":" value

connection_def  = piece_ref "-[" connection_body "]-" piece_ref
connection_body = anchor_props anchor_props connection_type?
                | compact_anchor compact_anchor compact_connection_type?
piece_ref       = CNAME

anchor_props    = "{" anchor_prop_list "}"
anchor_prop_list= anchor_prop ("," anchor_prop)*
anchor_prop     = ESCAPED_STRING ":" (ESCAPED_STRING | offset_value)
offset_value    = "FromMin" "(" NUMBER ")" | "FromMax" "(" NUMBER ")"

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

COMMENT         = "//" [^\n]*
CNAME           = /[a-zA-Z_][a-zA-Z0-9_]*/
NUMBER          = /[0-9]+(\.[0-9]+)?/
```

## Error Messages

| Error Type | Example | Cause |
|------------|---------|-------|
| DSLSyntaxError | "Unexpected token at line 5" | Invalid syntax |
| DSLSemanticError | "Unknown piece: foo" | Reference to undefined piece |
| DSLSemanticError | "Duplicate piece ID: leg_1" | Same ID used twice |
| DSLValidationError | "Invalid piece type: 3x4" | Unknown lumber type |
| DSLValidationError | "Unknown dowel preset: 9x99" | Non-existent preset |

## CLI Commands

```bash
# Validate syntax
nichiyou-daiku validate furniture.nd

# Generate report
nichiyou-daiku report furniture.nd -o report.md

# 3D view (requires build123d)
nichiyou-daiku view furniture.nd

# Export to STL/STEP (requires build123d)
nichiyou-daiku export furniture.nd -f stl
nichiyou-daiku export furniture.nd -f step -o model.step
```
