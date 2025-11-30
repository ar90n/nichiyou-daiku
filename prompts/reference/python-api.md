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
│   ├── assembly.py # Assembly
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
from nichiyou_daiku.dsl import parse_dsl, DSLError, DSLSyntaxError, DSLSemanticError
```

## Piece Module

### PieceType

```python
from nichiyou_daiku.core.piece import PieceType

class PieceType(Enum):
    PT_2x4 = "2x4"  # 89mm x 38mm cross-section
    PT_1x4 = "1x4"  # 89mm x 19mm cross-section

# Create from string
PieceType.of("2x4")  # Returns PieceType.PT_2x4
```

### Piece

```python
from nichiyou_daiku.core.piece import Piece, PieceType

class Piece(BaseModel, frozen=True):
    id: str          # Unique identifier
    type: PieceType  # Lumber type
    length: float    # Length in mm

# Factory method
piece = Piece.of(PieceType.PT_2x4, 720.0, "leg_1")
piece = Piece.of(PieceType.PT_1x4, 600.0)  # Auto-generates UUID
```

### get_shape

```python
from nichiyou_daiku.core.piece import get_shape, PieceType, Piece

# Get 2D cross-section
shape2d = get_shape(PieceType.PT_2x4)
shape2d.width   # 89.0
shape2d.height  # 38.0

# Get 3D dimensions
piece = Piece.of(PieceType.PT_2x4, 1000.0)
shape3d = get_shape(piece)
shape3d.width   # 89.0
shape3d.height  # 38.0
shape3d.length  # 1000.0
```

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

**Offset types:**
- `FromMin(value=n)`: n mm from start
- `FromMax(value=n)`: n mm from end

### BoundAnchor

```python
from nichiyou_daiku.core.anchor import BoundAnchor

class BoundAnchor(BaseModel, frozen=True):
    piece: Piece    # Associated piece
    anchor: Anchor  # Position on piece

bound = BoundAnchor(piece=leg, anchor=anchor)
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

# Dowel
dowel = DowelConnection(radius=4.0, depth=15.0)

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
    pilot_holes: dict[str, list[tuple[Point3D, Hole]]]
    label: str | None

# Create assembly from model
assembly = Assembly.of(model)
```

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
cross("top", "front") # "left" or "right"
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
leg -[FR>100 DB<0 D(:8x30)]- apron
"""
model = parse_dsl(dsl)

# Error handling
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
from nichiyou_daiku.shell import extract_resources, ResourceSummary

resources = extract_resources(assembly)
resources.pretty_print()
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

### 3D Export (requires build123d)

```python
from nichiyou_daiku.shell import assembly_to_build123d

compound = assembly_to_build123d(assembly, fillet_radius=5.0)

# Export to STL
compound.export_stl("model.stl")

# Export to STEP
compound.export_step("model.step")
```

## Complete Example

```python
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.geometry import FromMin, FromMax
from nichiyou_daiku.core.dowel import Dowel, as_spec as dowel_spec

# Create pieces
leg1 = Piece.of(PieceType.PT_2x4, 720.0, "leg1")
leg2 = Piece.of(PieceType.PT_2x4, 720.0, "leg2")
apron = Piece.of(PieceType.PT_2x4, 600.0, "apron")

# Define connections with dowel joints
conn1 = Connection.of_dowel(
    base=BoundAnchor(
        piece=leg1,
        anchor=Anchor(
            contact_face="front",
            edge_shared_face="right",
            offset=FromMax(value=100)
        )
    ),
    target=BoundAnchor(
        piece=apron,
        anchor=Anchor(
            contact_face="down",
            edge_shared_face="back",
            offset=FromMin(value=0)
        )
    ),
    spec=dowel_spec(Dowel.D8_L30),
)

conn2 = Connection.of_dowel(
    base=BoundAnchor(
        piece=leg2,
        anchor=Anchor(
            contact_face="front",
            edge_shared_face="left",
            offset=FromMax(value=100)
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

# Build model and assembly
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

leg1 -[FR>100 DB<0 D(:8x30)]- apron
leg2 -[FL>100 DB>0 D(:8x30)]- apron
"""

model = parse_dsl(dsl)
assembly = Assembly.of(model)
```
