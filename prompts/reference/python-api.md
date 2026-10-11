# Python API Reference

Complete Python API for the nichiyou-daiku library.

## Module Structure

```
nichiyou_daiku/
├── core/           # Pure data models
│   ├── piece.py    # Piece, PieceType
│   ├── anchor.py   # Anchor, BoundAnchor
│   ├── connection.py # Connection, ConnectionType
│   ├── model.py    # Model
│   ├── assembly/   # Assembly (3D placement, joints, pilot holes)
│   ├── dowel.py    # Dowel presets
│   ├── screw.py    # Screw presets
│   └── geometry/   # Offset, Face utilities
├── dsl/            # DSL parser
└── shell/          # External integrations
```

## Core Imports

```python
# Essential imports for furniture design
from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.connection import (
    Connection,
    VanillaConnection,
    DowelConnection,
    ScrewConnection,
)
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.geometry import FromMin, FromMax

# Fastener presets
from nichiyou_daiku.core.dowel import Dowel, as_spec as dowel_spec
from nichiyou_daiku.core.screw import (
    SlimScrew,
    CoarseThreadScrew,
    as_spec as screw_spec,
)

# DSL parsing
from nichiyou_daiku.dsl import parse_dsl, DSLError, DSLSyntaxError, DSLSemanticError, DSLValidationError
```

## Piece Module

### PieceType

```python
from nichiyou_daiku.core.piece import PieceType

class PieceType(Enum):
    PT_2x4 = "2x4"  # 89mm (width) x 38mm (thickness) cross-section
    PT_1x4 = "1x4"  # 89mm (width) x 19mm (thickness) cross-section

# Create from string
PieceType.of("2x4")  # Returns PieceType.PT_2x4
```

### Piece

```python
from nichiyou_daiku.core.piece import Piece, PieceType

class Piece(BaseModel, frozen=True):
    id: str          # Unique identifier
    type: PieceType  # Lumber type
    length: float    # Length in mm (must be > 0)

# Factory method
piece = Piece.of(PieceType.PT_2x4, 720.0, "leg_1")
piece = Piece.of(PieceType.PT_1x4, 600.0)  # Auto-generates UUID
```

### get_shape

```python
from nichiyou_daiku.core.piece import get_shape, PieceType, Piece

# Get 2D cross-section
shape2d = get_shape(PieceType.PT_2x4)
shape2d.width   # 89.0  (local X)
shape2d.height  # 38.0  (thickness, local Y)

# Get 3D dimensions
piece = Piece.of(PieceType.PT_2x4, 1000.0)
shape3d = get_shape(piece)
shape3d.width   # 89.0
shape3d.height  # 38.0
shape3d.length  # 1000.0  (local Z)
```

Each piece has its own local frame: X = width, Y = thickness (`height` in `Shape2D`/`Shape3D`), Z = length.

## Anchor Module

### Anchor

```python
from nichiyou_daiku.core.anchor import Anchor
from nichiyou_daiku.core.geometry import FromMin, FromMax

class Anchor(BaseModel, frozen=True):
    contact_face: Face        # Face touching other piece
    edge_shared_face: Face    # Face whose edge is shared
    offset: Offset            # Position along edge

# Create anchor
anchor = Anchor(
    contact_face="left",
    edge_shared_face="back",
    offset=FromMax(value=0)
)
```

**Face type:** `"top" | "down" | "left" | "right" | "front" | "back"`

| Face | Normal | Kind |
|------|--------|------|
| top / down | +Z / -Z | end faces (89 x thickness) |
| front / back | +Y / -Y | wide faces (89 x length) |
| right / left | +X / -X | narrow faces (thickness x length) |

`contact_face` and `edge_shared_face` must be adjacent (not the same, not opposite); `Anchor` raises `ValueError` otherwise. The anchor point lies on the edge where the two faces meet:

| Face pair | Edge runs along | `FromMin(v)` measured from | `FromMax(v)` measured from |
|-----------|-----------------|----------------------------|----------------------------|
| top/down + front/back | width (0-89) | left side | right side |
| top/down + left/right | thickness (0-38 / 0-19) | back side | front side |
| front/back + left/right | length (0-L) | down end | top end |

**Offset types:**
- `FromMin(value=n)`: n mm from the min end of the edge
- `FromMax(value=n)`: n mm from the max end of the edge

### BoundAnchor

```python
from nichiyou_daiku.core.anchor import BoundAnchor

class BoundAnchor(BaseModel, frozen=True):
    piece: Piece    # Associated piece
    anchor: Anchor  # Position on piece

leg = Piece.of(PieceType.PT_2x4, 720.0, "leg")
bound = BoundAnchor(piece=leg, anchor=anchor)  # ValueError if the offset exceeds the edge length
```

## Connection Module

### Connection Types

```python
from nichiyou_daiku.core.connection import (
    VanillaConnection,
    DowelConnection,
    ScrewConnection,
)

# Vanilla (no reinforcement)
vanilla = VanillaConnection()

# Dowel (depth = total dowel length; half goes into each piece)
dowel = DowelConnection(radius=4.0, depth=30.0)

# Screw
screw = ScrewConnection(diameter=3.3, length=50.0)
```

### Connection

```python
from nichiyou_daiku.core.connection import Connection

class Connection(BaseModel, frozen=True):
    base: BoundAnchor       # Base piece (stays fixed)
    target: BoundAnchor     # Target piece (attaches)
    type: ConnectionType    # Default: VanillaConnection()

# Placement: the contact faces touch, the edge_shared faces are flush,
# and the two anchor points coincide.

# Vanilla connection
conn = Connection(
    base=BoundAnchor(piece=leg, anchor=leg_anchor),
    target=BoundAnchor(piece=apron, anchor=apron_anchor),
)

# Dowel connection
conn = Connection.of_dowel(
    base=BoundAnchor(piece=leg, anchor=leg_anchor),
    target=BoundAnchor(piece=apron, anchor=apron_anchor),
    spec=dowel_spec(Dowel.D8_L30),
)

# Screw connection
conn = Connection.of_screw(
    base=BoundAnchor(piece=leg, anchor=leg_anchor),
    target=BoundAnchor(piece=apron, anchor=apron_anchor),
    spec=screw_spec(SlimScrew.D3_3_L50),
)
```

## Model Module

```python
from nichiyou_daiku.core.model import Model

class Model(BaseModel, frozen=True):
    pieces: dict[str, Piece]                       # ID -> Piece
    connections: dict[tuple[str, str], Connection] # (base_id, target_id) -> Connection
    label: str | None = None

# Create model
model = Model.of(
    pieces=[leg_1, leg_2, apron],
    connections=[conn1, conn2],
    label="My Table"
)
```

## Assembly Module

```python
from nichiyou_daiku.core.assembly import Assembly

class Assembly(BaseModel, frozen=True):
    model: Model
    boxes: dict[str, Box]      # Piece 3D positions
    joints: dict[str, Joint]   # Joint information
    joint_conns: list[tuple[str, str]]
    pilot_holes: dict[str, list[tuple[SurfacePoint, Hole]]]  # piece ID -> holes; SurfacePoint names the drilled face
    label: str | None

# Create assembly from model
assembly = Assembly.of(model)
```

Pilot holes: a dowel makes a hole of its diameter, length/2 deep, in each piece; a screw makes a through-hole in the target and a hole (length - target thickness) deep in the base; vanilla connections make no holes.

## Geometry Module

### Offset

```python
from nichiyou_daiku.core.geometry import FromMin, FromMax, Offset

class FromMin(BaseModel, frozen=True):
    value: float  # Distance from start in mm

class FromMax(BaseModel, frozen=True):
    value: float  # Distance from end in mm

Offset = FromMin | FromMax
```

### Face Utilities

```python
from nichiyou_daiku.core.geometry.face import opposite, cross, is_adjacent

opposite("top")       # "down"
opposite("left")      # "right"
cross("top", "front") # "left"
is_adjacent("top", "front")  # True
is_adjacent("top", "down")   # False
```

## Dowel Module

```python
from nichiyou_daiku.core.dowel import Dowel, DowelSpec, as_spec

class Dowel(Enum):
    D6_L25 = "6x25"
    D6_L30 = "6x30"
    D8_L25 = "8x25"
    D8_L30 = "8x30"
    D8_L40 = "8x40"
    D10_L30 = "10x30"
    D10_L40 = "10x40"
    D12_L40 = "12x40"

# Create from string
dowel = Dowel.of("8x30")

# Get specification
spec = as_spec(dowel)
spec.diameter  # 8.0
spec.length    # 30.0
```

## Screw Module

```python
from nichiyou_daiku.core.screw import (
    SlimScrew,
    CoarseThreadScrew,
    ScrewSpec,
    as_spec,
)

class SlimScrew(Enum):
    D3_3_L25 = "3.3x25"
    D3_3_L30 = "3.3x30"
    D3_3_L35 = "3.3x35"
    D3_3_L40 = "3.3x40"
    D3_3_L45 = "3.3x45"
    D3_3_L50 = "3.3x50"
    D3_8_L55 = "3.8x55"
    D3_8_L60 = "3.8x60"
    D3_8_L65 = "3.8x65"
    D3_8_L70 = "3.8x70"
    D3_8_L75 = "3.8x75"
    D4_2_L90 = "4.2x90"

class CoarseThreadScrew(Enum):
    D3_8_L25 = "3.8x25"
    D3_8_L30 = "3.8x30"
    D3_8_L35 = "3.8x35"
    D3_8_L40 = "3.8x40"
    D3_8_L45 = "3.8x45"
    D3_8_L50 = "3.8x50"
    D3_8_L57 = "3.8x57"
    D4_2_L65 = "4.2x65"
    D4_2_L75 = "4.2x75"
    D4_5_L90 = "4.5x90"
    D4_5_L100 = "4.5x100"
    D5_2_L120 = "5.2x120"

# Usage
screw = SlimScrew.of("3.3x50")
spec = as_spec(screw)
```

## DSL Module

```python
from nichiyou_daiku.dsl import (
    parse_dsl,
    DSLError,
    DSLSyntaxError,
    DSLSemanticError,
    DSLValidationError,
)

# Parse DSL string
dsl = """
(leg:2x4 =720)
(apron:2x4 =600)
leg -[LB>0 DB>0 D(:8x30)]- apron
"""
model = parse_dsl(dsl)

# Error handling ("FB": front and back are opposite faces)
invalid_dsl = """
(leg:2x4 =720)
(apron:2x4 =600)
leg -[FB<0 DB>0]- apron
"""
try:
    model = parse_dsl(invalid_dsl)
except DSLSyntaxError as e:
    print(f"Syntax error: {e}")
except DSLSemanticError as e:
    print(f"Semantic error: {e}")
except DSLValidationError as e:
    print(f"Validation error: {e}")
```

## Shell Module

### Resource Extraction

```python
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.shell import extract_resources, ResourceSummary

assembly = Assembly.of(model)
resources = extract_resources(assembly)  # takes an Assembly, not a Model
print(resources.pretty_print())
```

### Report Generation

```python
from nichiyou_daiku.shell import generate_markdown_report

report = generate_markdown_report(
    resources,
    project_name="My Table",
    include_cut_diagram=True,
)
print(report)
```

The cut plan allows a 3mm saw kerf per cut and warns about pieces longer than any stock board.

### 3D Export (requires build123d)

```python
from build123d import export_stl, export_step
from nichiyou_daiku.shell import assembly_to_build123d

compound = assembly_to_build123d(assembly, fillet_radius=5.0)

# Export to STL
export_stl(compound, "model.stl")

# Export to STEP
export_step(compound, "model.step")
```

## Complete Example

Two legs and an apron between them, flush with the leg tops (the front apron of the verified table pattern).

```python
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.geometry import FromMax
from nichiyou_daiku.core.dowel import Dowel, as_spec as dowel_spec

# Create pieces
leg1 = Piece.of(PieceType.PT_2x4, 720.0, "leg1")
leg2 = Piece.of(PieceType.PT_2x4, 720.0, "leg2")
apron = Piece.of(PieceType.PT_2x4, 600.0, "apron")

# leg1 -[LB>0 DB>0 D(:8x30)]- apron
conn1 = Connection.of_dowel(
    base=BoundAnchor(
        piece=leg1,
        anchor=Anchor(
            contact_face="left",
            edge_shared_face="back",
            offset=FromMax(value=0)
        )
    ),
    target=BoundAnchor(
        piece=apron,
        anchor=Anchor(
            contact_face="down",
            edge_shared_face="back",
            offset=FromMax(value=0)
        )
    ),
    spec=dowel_spec(Dowel.D8_L30),
)

# leg2 -[RF>0 TF>0 D(:8x30)]- apron
conn2 = Connection.of_dowel(
    base=BoundAnchor(
        piece=leg2,
        anchor=Anchor(
            contact_face="right",
            edge_shared_face="front",
            offset=FromMax(value=0)
        )
    ),
    target=BoundAnchor(
        piece=apron,
        anchor=Anchor(
            contact_face="top",
            edge_shared_face="front",
            offset=FromMax(value=0)
        )
    ),
    spec=dowel_spec(Dowel.D8_L30),
)

# Build model and assembly (overall 778 x 38 x 720mm)
model = Model.of(
    pieces=[leg1, leg2, apron],
    connections=[conn1, conn2],
    label="Simple Frame"
)
assembly = Assembly.of(model)
```

## Alternative: Using DSL

```python
from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.core.assembly import Assembly

dsl = """
// Simple frame with dowel joints
(leg1:2x4 =720)
(leg2:2x4 =720)
(apron:2x4 =600)

leg1 -[LB>0 DB>0 D(:8x30)]- apron
leg2 -[RF>0 TF>0 D(:8x30)]- apron
"""

model = parse_dsl(dsl)
assembly = Assembly.of(model)
```
