# nichiyou-daiku LLM Prompt Template

This document provides prompt templates for using LLMs to generate nichiyou-daiku design files (`.nd` scripts or Python code) from user specifications.

## Table of Contents

- [Overview](#overview)
- [User Input Format](#user-input-format)
- [System Prompt](#system-prompt)
- [Output Examples](#output-examples)
- [Usage Tips](#usage-tips)

---

## Overview

This system enables users to describe furniture designs in a structured format, which an LLM then converts into executable nichiyou-daiku code.

**Workflow:**
1. User fills in the **Furniture Specification Form**
2. LLM receives the form + **System Prompt** (with API/DSL specs)
3. LLM generates `.nd` script or Python code

---

## User Input Format

Users should fill in the following specification form. Copy and modify as needed.

### Furniture Specification Form

```markdown
# Furniture Design Specification

## Basic Information
- **Name**: [e.g., "Kitchen Shelf", "Work Desk"]
- **Type**: [table / shelf / rack / bench / other]
- **Output Format**: [nd / python]

## Dimensions (mm)
- **Width**: [e.g., 800]
- **Depth**: [e.g., 400]
- **Height**: [e.g., 720]

## Material
- **Primary**: [2x4 / 1x4]
- **Secondary** (optional): [2x4 / 1x4 / none]

## Structure

### Legs
- **Count**: [4 / 2 / 0]
- **Position**: [corner / edge / center]
- **Inset**: [yes / no] (if yes, legs are inside the frame)

### Horizontal Supports
- **Aprons**: [yes / no]
- **Apron Position**: [top / bottom / both / custom: ___mm from top/bottom]
- **Cross Brace**: [yes / no]

### Surfaces
- **Top Surface**: [yes / no]
- **Top Material**: [2x4 / 1x4]
- **Shelves**: [count: 0, 1, 2, ...]
- **Shelf Heights**: [e.g., "200mm, 400mm from bottom"]

## Joints
- **Type**: [vanilla / dowel / screw]
- **Dowel Preset**: [6x25 / 6x30 / 8x25 / 8x30 / 8x40 / 10x30 / 10x40 / 12x40]
- **Screw Preset**: [Slim:3.3x50 / Coarse:3.8x57 / etc.]

## Additional Notes
[Any special requirements, constraints, or design preferences]
```

### Example: Filled Form

```markdown
# Furniture Design Specification

## Basic Information
- **Name**: "Simple Side Table"
- **Type**: table
- **Output Format**: nd

## Dimensions (mm)
- **Width**: 500
- **Depth**: 400
- **Height**: 600

## Material
- **Primary**: 2x4
- **Secondary**: none

## Structure

### Legs
- **Count**: 4
- **Position**: corner
- **Inset**: yes

### Horizontal Supports
- **Aprons**: yes
- **Apron Position**: top (flush with leg tops)
- **Cross Brace**: no

### Surfaces
- **Top Surface**: yes
- **Top Material**: 2x4
- **Shelves**: 0

## Joints
- **Type**: dowel
- **Dowel Preset**: 8x30

## Additional Notes
- Table top boards should run along the depth direction
- Keep design simple and sturdy
```

---

## System Prompt

The following system prompt should be provided to the LLM along with the user's specification form.

### System Prompt (English)

````markdown
You are a woodworking CAD code generator for the nichiyou-daiku library. Your task is to convert furniture specifications into executable code.

## Your Role

Given a furniture specification form, generate either:
1. **ND Script** (`.nd` file) - Domain-specific language for simple designs
2. **Python Code** (`.py` file) - Full Python code using the nichiyou-daiku API

## Output Guidelines

### For ND Scripts
- Use compact notation (preferred): `(piece_id:2x4 =length)` and `piece1 -[TF<0 BD<0]- piece2`
- Add comments explaining the structure
- Calculate piece lengths correctly based on dimensions and lumber thickness

### For Python Code
- Import from `nichiyou_daiku.core` modules
- Use descriptive variable names
- Include dimension constants at the top
- Add comments for each section

## Critical Rules

1. **Piece Dimensions**:
   - 2x4: width=89mm, height=38mm
   - 1x4: width=89mm, height=19mm
   - Calculate actual piece lengths accounting for joints

2. **Connection Model**:
   - Pieces connect by sharing an EDGE (not just touching faces)
   - `contact_face`: The face touching the other piece
   - `edge_shared_face`: The face whose edge is shared (must be adjacent to contact_face)
   - `offset`: Position along the shared edge (FromMin or FromMax)

3. **Valid Face Combinations**:
   - Adjacent faces only: top+front ✓, top+left ✓
   - Not opposite faces: top+down ✗, left+right ✗

4. **Face Abbreviations** (for ND scripts):
   - T=top, D=down, L=left, R=right, F=front, B=back
   - `<n` = FromMin(n), `>n` = FromMax(n)

5. **Joint Types**:
   - Vanilla: `piece1 -[TF<0 BD<0]- piece2`
   - Dowel: `piece1 -[TF<0 BD<0 D(:8x30)]- piece2`
   - Screw: `piece1 -[BF<0 FB<0 S(Slim:3.3x50)]- piece2`
   - Note: Screw connections require target contact_face to be 'front' or 'back'

## DSL Quick Reference

### Piece Definition
```
(piece_id:2x4 =length)    // 2x4 lumber, length in mm
(piece_id:1x4 =length)    // 1x4 lumber, length in mm
```

### Connection Definition
```
base_piece -[BASE_ANCHOR TARGET_ANCHOR CONNECTION_TYPE?]- target_piece

// Anchor format: XY<offset or XY>offset
// X = contact_face (T/D/L/R/F/B)
// Y = edge_shared_face (T/D/L/R/F/B)
// < = FromMin, > = FromMax
```

### Examples
```nd
// Simple corner joint
(piece_a:2x4 =400)
(piece_b:2x4 =400)
piece_a -[TF<0 BD<0]- piece_b

// With dowel
piece_a -[TF<0 BD<0 D(:8x30)]- piece_b

// With screw
piece_a -[BF<0 FB<0 S(Slim:3.3x50)]- piece_b
```

## Dowel Presets
| Preset | Diameter | Length |
|--------|----------|--------|
| 6x25   | 6mm      | 25mm   |
| 6x30   | 6mm      | 30mm   |
| 8x25   | 8mm      | 25mm   |
| 8x30   | 8mm      | 30mm   |
| 8x40   | 8mm      | 40mm   |
| 10x30  | 10mm     | 30mm   |
| 10x40  | 10mm     | 40mm   |
| 12x40  | 12mm     | 40mm   |

## Screw Presets

### Slim Screws
| Preset | Diameter | Length |
|--------|----------|--------|
| Slim:3.3x25 | 3.3mm | 25mm |
| Slim:3.3x30 | 3.3mm | 30mm |
| Slim:3.3x35 | 3.3mm | 35mm |
| Slim:3.3x40 | 3.3mm | 40mm |
| Slim:3.3x45 | 3.3mm | 45mm |
| Slim:3.3x50 | 3.3mm | 50mm |
| Slim:3.8x55 | 3.8mm | 55mm |
| Slim:3.8x65 | 3.8mm | 65mm |

### Coarse Thread Screws
| Preset | Diameter | Length |
|--------|----------|--------|
| Coarse:3.8x25 | 3.8mm | 25mm |
| Coarse:3.8x32 | 3.8mm | 32mm |
| Coarse:3.8x45 | 3.8mm | 45mm |
| Coarse:3.8x57 | 3.8mm | 57mm |
| Coarse:4.2x65 | 4.2mm | 65mm |
| Coarse:4.2x75 | 4.2mm | 75mm |

## Output Format

When generating code:
1. Start with a comment header describing the design
2. Define all pieces first
3. Define connections grouped by structural role (legs→aprons, aprons→top, etc.)
4. For Python: end with Model.of() and Assembly.of()
5. Verify all piece references exist before using in connections
````

---

## Output Examples

### Example 1: ND Script Output

For the "Simple Side Table" specification above:

```nd
// Simple Side Table
// Dimensions: 500mm x 400mm x 600mm
// Material: 2x4
// Joints: Dowel (8x30)

// ============================================================================
// PIECES
// ============================================================================

// Legs (4x)
// Height = 600mm (full table height, aprons flush at top)
(leg_fl:2x4 =600)  // Front-left
(leg_fr:2x4 =600)  // Front-right
(leg_bl:2x4 =600)  // Back-left
(leg_br:2x4 =600)  // Back-right

// Aprons
// Front/Back length = 500 - 2*89 = 322mm (width minus two leg widths)
// Left/Right length = 400 - 2*38 = 324mm (depth minus two leg heights)
(apron_front:2x4 =322)
(apron_back:2x4 =322)
(apron_left:2x4 =324)
(apron_right:2x4 =324)

// Table top pieces (run along depth direction)
// Each piece is 400mm long (full depth)
// Number of pieces: floor(322 / 89) = 3 pieces with gaps
(top_1:2x4 =400)
(top_2:2x4 =400)
(top_3:2x4 =400)

// ============================================================================
// CONNECTIONS
// ============================================================================

// Front apron to legs (flush at top)
leg_fl -[LB>0 DB>0 D(:8x30)]- apron_front
leg_fr -[RF>0 TF>0 D(:8x30)]- apron_front

// Back apron to legs
leg_bl -[LB>0 DB>0 D(:8x30)]- apron_back
leg_br -[RF>0 TF>0 D(:8x30)]- apron_back

// Left apron to legs
leg_fl -[BR>0 DB<0 D(:8x30)]- apron_left
leg_bl -[FR>0 TB<0 D(:8x30)]- apron_left

// Right apron to legs
leg_fr -[BL>0 DF<0 D(:8x30)]- apron_right
leg_br -[FL>0 TF<0 D(:8x30)]- apron_right

// Table top connections (to front apron)
apron_front -[RF<0 BT<0 D(:8x30)]- top_1
apron_front -[RF<116.5 BT<0 D(:8x30)]- top_2
apron_front -[RF<233 BT<0 D(:8x30)]- top_3
```

### Example 2: Python Code Output

```python
"""Simple Side Table
Dimensions: 500mm x 400mm x 600mm
Material: 2x4
Joints: Dowel (8x30)
"""

from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.geometry import FromMax, FromMin
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.dowel import Dowel, as_spec

# ============================================================================
# DIMENSIONS
# ============================================================================
TABLE_WIDTH = 500.0   # mm
TABLE_DEPTH = 400.0   # mm
TABLE_HEIGHT = 600.0  # mm

# Lumber dimensions
LUMBER_WIDTH = get_shape(PieceType.PT_2x4).width    # 89mm
LUMBER_HEIGHT = get_shape(PieceType.PT_2x4).height  # 38mm

# Calculated lengths
APRON_FRONT_BACK = TABLE_WIDTH - 2 * LUMBER_WIDTH   # 322mm
APRON_LEFT_RIGHT = TABLE_DEPTH - 2 * LUMBER_HEIGHT  # 324mm

# Joint specification
DOWEL_SPEC = as_spec(Dowel.D8_L30)

# ============================================================================
# PIECES
# ============================================================================

# Legs
leg_fl = Piece.of(PieceType.PT_2x4, TABLE_HEIGHT, "leg_fl")
leg_fr = Piece.of(PieceType.PT_2x4, TABLE_HEIGHT, "leg_fr")
leg_bl = Piece.of(PieceType.PT_2x4, TABLE_HEIGHT, "leg_bl")
leg_br = Piece.of(PieceType.PT_2x4, TABLE_HEIGHT, "leg_br")

# Aprons
apron_front = Piece.of(PieceType.PT_2x4, APRON_FRONT_BACK, "apron_front")
apron_back = Piece.of(PieceType.PT_2x4, APRON_FRONT_BACK, "apron_back")
apron_left = Piece.of(PieceType.PT_2x4, APRON_LEFT_RIGHT, "apron_left")
apron_right = Piece.of(PieceType.PT_2x4, APRON_LEFT_RIGHT, "apron_right")

# Table top pieces
top_1 = Piece.of(PieceType.PT_2x4, TABLE_DEPTH, "top_1")
top_2 = Piece.of(PieceType.PT_2x4, TABLE_DEPTH, "top_2")
top_3 = Piece.of(PieceType.PT_2x4, TABLE_DEPTH, "top_3")

# ============================================================================
# CONNECTIONS
# ============================================================================
connections = []

# Front apron connections
connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=leg_fl,
        anchor=Anchor(contact_face="left", edge_shared_face="back", offset=FromMax(value=0))
    ),
    target=BoundAnchor(
        piece=apron_front,
        anchor=Anchor(contact_face="down", edge_shared_face="back", offset=FromMax(value=0))
    ),
    spec=DOWEL_SPEC,
))

connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=leg_fr,
        anchor=Anchor(contact_face="right", edge_shared_face="front", offset=FromMax(value=0))
    ),
    target=BoundAnchor(
        piece=apron_front,
        anchor=Anchor(contact_face="top", edge_shared_face="front", offset=FromMax(value=0))
    ),
    spec=DOWEL_SPEC,
))

# Back apron connections
connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=leg_bl,
        anchor=Anchor(contact_face="left", edge_shared_face="back", offset=FromMax(value=0))
    ),
    target=BoundAnchor(
        piece=apron_back,
        anchor=Anchor(contact_face="down", edge_shared_face="back", offset=FromMax(value=0))
    ),
    spec=DOWEL_SPEC,
))

connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=leg_br,
        anchor=Anchor(contact_face="right", edge_shared_face="front", offset=FromMax(value=0))
    ),
    target=BoundAnchor(
        piece=apron_back,
        anchor=Anchor(contact_face="top", edge_shared_face="front", offset=FromMax(value=0))
    ),
    spec=DOWEL_SPEC,
))

# Left apron connections
connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=leg_fl,
        anchor=Anchor(contact_face="back", edge_shared_face="right", offset=FromMax(value=0))
    ),
    target=BoundAnchor(
        piece=apron_left,
        anchor=Anchor(contact_face="down", edge_shared_face="back", offset=FromMin(value=0))
    ),
    spec=DOWEL_SPEC,
))

connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=leg_bl,
        anchor=Anchor(contact_face="front", edge_shared_face="right", offset=FromMax(value=0))
    ),
    target=BoundAnchor(
        piece=apron_left,
        anchor=Anchor(contact_face="top", edge_shared_face="back", offset=FromMin(value=0))
    ),
    spec=DOWEL_SPEC,
))

# Right apron connections
connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=leg_fr,
        anchor=Anchor(contact_face="back", edge_shared_face="left", offset=FromMax(value=0))
    ),
    target=BoundAnchor(
        piece=apron_right,
        anchor=Anchor(contact_face="down", edge_shared_face="front", offset=FromMin(value=0))
    ),
    spec=DOWEL_SPEC,
))

connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=leg_br,
        anchor=Anchor(contact_face="front", edge_shared_face="left", offset=FromMax(value=0))
    ),
    target=BoundAnchor(
        piece=apron_right,
        anchor=Anchor(contact_face="top", edge_shared_face="front", offset=FromMin(value=0))
    ),
    spec=DOWEL_SPEC,
))

# Table top connections
top_offset = (APRON_FRONT_BACK - 3 * LUMBER_WIDTH) / 2  # Center the 3 boards
connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=apron_front,
        anchor=Anchor(contact_face="right", edge_shared_face="front", offset=FromMin(value=0))
    ),
    target=BoundAnchor(
        piece=top_1,
        anchor=Anchor(contact_face="back", edge_shared_face="top", offset=FromMin(value=0))
    ),
    spec=DOWEL_SPEC,
))

connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=apron_front,
        anchor=Anchor(contact_face="right", edge_shared_face="front", offset=FromMin(value=LUMBER_WIDTH + top_offset))
    ),
    target=BoundAnchor(
        piece=top_2,
        anchor=Anchor(contact_face="back", edge_shared_face="top", offset=FromMin(value=0))
    ),
    spec=DOWEL_SPEC,
))

connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=apron_front,
        anchor=Anchor(contact_face="right", edge_shared_face="front", offset=FromMin(value=2 * LUMBER_WIDTH + 2 * top_offset))
    ),
    target=BoundAnchor(
        piece=top_3,
        anchor=Anchor(contact_face="back", edge_shared_face="top", offset=FromMin(value=0))
    ),
    spec=DOWEL_SPEC,
))

# ============================================================================
# BUILD MODEL
# ============================================================================
model = Model.of(
    pieces=[
        leg_fl, leg_fr, leg_bl, leg_br,
        apron_front, apron_back, apron_left, apron_right,
        top_1, top_2, top_3,
    ],
    connections=connections,
    label="simple_side_table",
)

# ============================================================================
# CREATE ASSEMBLY
# ============================================================================
assembly = Assembly.of(model)

print(f"Simple Side Table: {TABLE_WIDTH}mm x {TABLE_DEPTH}mm x {TABLE_HEIGHT}mm")
print(f"Pieces: {len(model.pieces)}, Connections: {len(model.connections)}")

# Optional: Visualize with build123d
# from nichiyou_daiku.shell import assembly_to_build123d
# from ocp_vscode import show
# compound = assembly_to_build123d(assembly, fillet_radius=2.0)
# show(compound)
```

---

## Usage Tips

### For Best Results

1. **Be specific about dimensions** - Provide exact measurements in mm
2. **Clarify leg positioning** - "Inset" means legs are inside the frame; "flush" means at edges
3. **Specify joint preferences** - Different joints suit different uses (dowels for strength, screws for easy disassembly)
4. **Describe the structure** - Mention shelf positions, brace locations, etc.

### Common Patterns

| Pattern | Description | Typical Structure |
|---------|-------------|-------------------|
| Table | Flat top surface on legs | 4 legs + 4 aprons + top boards |
| Shelf | Multiple horizontal surfaces | 4 legs + aprons at each shelf level |
| Bench | Low, sturdy seating | 4 legs + stretchers + seat boards |
| Rack | Open storage | Legs + cross braces + optional surfaces |

### Troubleshooting

If the generated code doesn't work:
1. Check that all piece IDs are unique
2. Verify face combinations are adjacent (not opposite)
3. Ensure offsets don't exceed piece dimensions
4. For screws, confirm target contact_face is 'front' or 'back'

---

## Quick Reference Card

### Face Names
```
       top (T)
         │
left (L)─┼─right (R)
         │
      down (D)

back (B)─┼─front (F)
```

### Offset Notation
```
<n = FromMin(n)  // n mm from start
>n = FromMax(n)  // n mm from end
```

### Connection Format
```
base -[XY<offset XY<offset TYPE]- target

X = contact_face (T/D/L/R/F/B)
Y = edge_shared_face (T/D/L/R/F/B)
TYPE = V (vanilla) | D(:DxL) (dowel) | S(Type:DxL) (screw)
```

### Lumber Dimensions (mm)
```
2x4: width=89, height=38
1x4: width=89, height=19
```
