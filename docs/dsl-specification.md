# nichiyou-daiku DSL Specification

The nichiyou-daiku DSL (`.nd` files) is a domain-specific language for concisely describing woodworking furniture designs. Using a Cypher-like syntax, you can define lumber pieces and their connections.

## Table of Contents

- [Basic Structure](#basic-structure)
- [Comments](#comments)
- [Piece Definition](#piece-definition)
- [Connection Definition](#connection-definition)
- [Connection Types](#connection-types)
- [Complete Examples](#complete-examples)
- [CLI Tools](#cli-tools)
- [Grammar (EBNF)](#grammar-ebnf)

## Basic Structure

An `.nd` file consists of the following elements:

1. **Comments** - Lines starting with `//`
2. **Piece Definitions** - Lumber piece declarations
3. **Connection Definitions** - Connections between pieces

```nd
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

## Piece Definition

Defines a lumber piece.

### Syntax

```
(piece_id:piece_type =length)
(piece_id:piece_type {"length": length})
```

### Parameters

| Parameter | Description | Required |
|-----------|-------------|----------|
| `piece_id` | Unique identifier for the piece | Yes |
| `piece_type` | Type of lumber (`1x4`, `2x4`) | Yes |
| `length` | Length in millimeters | Yes |

### Lumber Types

| Type | Width (mm) | Height (mm) | Description |
|------|------------|-------------|-------------|
| `1x4` | 89 | 19 | One-by-four lumber |
| `2x4` | 89 | 38 | Two-by-four lumber |

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

### Connection Model

In nichiyou-daiku, **two pieces always connect by sharing an edge**. This is a fundamental constraint that models real-world woodworking joints.

#### How Connections Work

Each piece is a rectangular box with 6 faces (top, down, left, right, front, back) and 12 edges. When two pieces connect:

1. **Contact Face**: The face of each piece that touches the other piece
2. **Edge Shared Face**: The face whose edge is shared at the connection point
3. **Offset**: Position along the shared edge

```
         ┌─────────────────┐
         │                 │
         │   BASE PIECE    │
         │                 │
         └────────┬────────┘
                  │ ← Contact faces touch here
         ┌────────┴────────┐
         │                 │
         │  TARGET PIECE   │
         │                 │
         └─────────────────┘
```

#### Edge Sharing Constraint

The contact faces of both pieces must share a common edge. This means:

- The **contact_face** determines which face touches the other piece
- The **edge_shared_face** determines which edge of the contact face is aligned
- The two pieces meet at the edge formed by contact_face ∩ edge_shared_face

```
Example: T-joint connection

       edge_shared_face = "front"
              ↓
    ┌─────────┼─────────┐
    │         │         │
    │   contact_face    │  ← BASE (horizontal)
    │      = "top"      │
    └─────────┴─────────┘
              │
    ┌─────────┴─────────┐
    │   contact_face    │
    │     = "down"      │  ← TARGET (vertical)
    │         │         │
    │ edge_shared_face  │
    │    = "front"      │
    └─────────┴─────────┘
```

#### Anchor Components

An **anchor** defines a specific point on a piece where a connection occurs:

| Component | Description |
|-----------|-------------|
| `contact_face` | The face that touches the other piece |
| `edge_shared_face` | The face whose edge is shared with contact_face |
| `offset` | Distance along the shared edge |

**Valid face combinations**: The contact_face and edge_shared_face must be adjacent (not opposite). For example:
- ✓ `top` + `front` (adjacent faces)
- ✓ `left` + `back` (adjacent faces)
- ✗ `top` + `down` (opposite faces - invalid)
- ✗ `left` + `right` (opposite faces - invalid)

### Syntax

```
base_piece -[base_anchor target_anchor connection_type?]- target_piece
```

### Anchor Notation

An anchor specifies which face of a piece connects and at what position.

#### Compact Notation (Recommended)

```
XY<offset  or  XY>offset
```

- **X**: Contact face
- **Y**: Edge shared face
- **<offset**: FromMin (offset from minimum position)
- **>offset**: FromMax (offset from maximum position)

#### Face Abbreviations

| Abbrev | Face | Description |
|--------|------|-------------|
| `T` | top | Top face |
| `D` | down | Bottom face |
| `L` | left | Left face |
| `R` | right | Right face |
| `F` | front | Front face |
| `B` | back | Back face |

#### Offset

| Notation | Meaning | Description |
|----------|---------|-------------|
| `<0` | FromMin(0) | 0mm from minimum position |
| `<100` | FromMin(100) | 100mm from minimum position |
| `>0` | FromMax(0) | 0mm from maximum position |
| `>50` | FromMax(50) | 50mm from maximum position |

### Examples

```nd
// Connect leg_1's left-back edge at max position
// to apron_front's down-back edge at max position
leg_1 -[LB>0 DB>0]- apron_front

// Connect leg_1's back-right edge at 100mm from min
// to apron_left's down-back edge at min position
leg_1 -[BR<100 DB<0]- apron_left
```

### JSON Format (Advanced Usage)

```nd
piece1 -[{"contact_face": "top", "edge_shared_face": "front", "offset": FromMin(0)}
         {"contact_face": "down", "edge_shared_face": "left", "offset": FromMax(100)}]- piece2
```

## Connection Types

Specifies the type of connection. Defaults to `V` (vanilla) if omitted.

### Vanilla Connection (V)

Default connection with no special reinforcement.

```nd
piece1 -[TF<0 BD<0]- piece2        // Implicit Vanilla
piece1 -[TF<0 BD<0 V]- piece2      // Explicit Vanilla
```

### Dowel Connection (D)

Connection using wooden dowels.

#### Numeric Specification

```nd
piece1 -[TF<0 BD<0 D(radius, depth)]- piece2
```

- `radius`: Dowel radius in mm
- `depth`: Dowel depth in mm

#### Preset Specification

```nd
piece1 -[TF<0 BD<0 D(:diameter x length)]- piece2
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

#### Examples

```nd
// Numeric: radius 4mm, depth 20mm dowel
piece1 -[TF<0 BD<0 D(4.0, 20.0)]- piece2

// Preset: 8mm diameter, 30mm length dowel
piece1 -[TF<0 BD<0 D(:8x30)]- piece2
```

### Screw Connection (S)

Connection using screws.

#### Numeric Specification

```nd
piece1 -[TF<0 BD<0 S(diameter, length)]- piece2
```

- `diameter`: Screw diameter in mm
- `length`: Screw length in mm

#### Preset Specification

```nd
piece1 -[TF<0 BD<0 S(Type:diameter x length)]- piece2
```

**Slim Screws**

| Preset | Diameter (mm) | Length (mm) |
|--------|---------------|-------------|
| `Slim:3.3x30` | 3.3 | 30 |
| `Slim:3.3x40` | 3.3 | 40 |
| `Slim:3.3x50` | 3.3 | 50 |
| `Slim:3.3x65` | 3.3 | 65 |
| `Slim:3.8x30` | 3.8 | 30 |
| `Slim:3.8x40` | 3.8 | 40 |
| `Slim:3.8x50` | 3.8 | 50 |
| `Slim:3.8x65` | 3.8 | 65 |
| `Slim:4.2x50` | 4.2 | 50 |
| `Slim:4.2x65` | 4.2 | 65 |
| `Slim:4.2x75` | 4.2 | 75 |

**Coarse Thread Screws**

| Preset | Diameter (mm) | Length (mm) |
|--------|---------------|-------------|
| `Coarse:3.8x32` | 3.8 | 32 |
| `Coarse:3.8x38` | 3.8 | 38 |
| `Coarse:3.8x45` | 3.8 | 45 |
| `Coarse:3.8x51` | 3.8 | 51 |
| `Coarse:3.8x57` | 3.8 | 57 |
| `Coarse:3.8x65` | 3.8 | 65 |
| `Coarse:3.8x75` | 3.8 | 75 |
| `Coarse:3.8x90` | 3.8 | 90 |
| `Coarse:4.2x65` | 4.2 | 65 |
| `Coarse:4.2x75` | 4.2 | 75 |
| `Coarse:4.2x90` | 4.2 | 90 |

#### Examples

```nd
// Numeric: 3.5mm diameter, 50mm length screw
piece1 -[BF<0 FB<0 S(3.5, 50)]- piece2

// Preset: Slim screw 3.3x50
piece1 -[BF<0 FB<0 S(Slim:3.3x50)]- piece2

// Preset: Coarse thread 3.8x57
piece1 -[BF<0 FB<0 S(Coarse:3.8x57)]- piece2
```

## Complete Examples

### Corner Joint

```nd
// Corner joint sample
(corner_piece_a:2x4 =400)
(corner_piece_b:2x4 =400)

corner_piece_a -[TF<0 BD<0]- corner_piece_b
```

### Simple Table

```nd
// Simple Table Design
// Four-legged table

// Legs
(leg_1:2x4 =720)
(leg_2:2x4 =720)
(leg_3:2x4 =720)
(leg_4:2x4 =720)

// Aprons
(apron_front:2x4 =622)
(apron_back:2x4 =622)
(apron_left:2x4 =524)
(apron_right:2x4 =524)

// Table top pieces
(table_top_1:2x4 =600)
(table_top_2:2x4 =600)

// Leg to apron connections
leg_1 -[LB>0 DB>0]- apron_front
leg_2 -[RF>0 TF>0]- apron_front
leg_3 -[LB>0 DB>0]- apron_back
leg_4 -[RF>0 TF>0]- apron_back

// Side apron connections
leg_1 -[BR<100 DB<0]- apron_left
leg_3 -[FR<100 TB<0]- apron_left

// Table top connections
table_top_1 -[BD<0 TF<0]- leg_1
table_top_2 -[BD<0 TF<0]- leg_2
```

### Shelf with Dowel Joints

```nd
// Shelf with dowel connections
(left_side:2x4 =800)
(right_side:2x4 =800)
(shelf:2x4 =600)

// Using dowel presets
left_side -[RT>100 FT<50 D(:8x30)]- shelf
right_side -[LT>100 FT<50 D(:8x30)]- shelf
```

## CLI Tools

### Syntax Validation

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

## Grammar (EBNF)

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

anchor_props         = "{" anchor_prop_list? "}"
anchor_prop_list     = anchor_prop ("," anchor_prop)*
anchor_prop          = ESCAPED_STRING ":" (ESCAPED_STRING | offset_value)
offset_value         = "FromMin" "(" NUMBER ")" | "FromMax" "(" NUMBER ")"

compact_anchor       = COMPACT_FACE COMPACT_FACE compact_offset
compact_offset       = "<" NUMBER | ">" NUMBER
COMPACT_FACE         = "T" | "D" | "L" | "R" | "F" | "B"

compact_connection_type = "V" | dowel_compact | screw_compact
dowel_compact           = "D(" (dowel_preset | dowel_numeric) ")"
dowel_preset            = ":" NUMBER "x" NUMBER
dowel_numeric           = NUMBER "," NUMBER
screw_compact           = "S(" (screw_preset | screw_numeric) ")"
screw_preset            = SCREW_TYPE ":" NUMBER "x" NUMBER
screw_numeric           = NUMBER "," NUMBER
SCREW_TYPE              = "Slim" | "Coarse"

COMMENT         = "//" [^\n]*
```

## Error Messages

### Syntax Errors

```
DSLSyntaxError: Unexpected token at line 5, column 10
```

### Semantic Errors

```
DSLSemanticError: Unknown piece reference: unknown_piece
DSLSemanticError: Duplicate piece ID: leg_1
```

### Validation Errors

```
DSLValidationError: Invalid piece type: 3x4
DSLValidationError: Unknown dowel preset: 9x99
DSLValidationError: Unknown Slim screw preset: 3.0x100
```
