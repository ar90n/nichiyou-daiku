# nichiyou-daiku API Specification

This document describes the Python API for the nichiyou-daiku woodworking CAD library.

## Table of Contents

- [Overview](#overview)
- [Core Module](#core-module)
  - [Piece](#piece)
  - [Anchor](#anchor)
  - [Connection](#connection)
  - [Model](#model)
  - [Assembly](#assembly)
- [Geometry Module](#geometry-module)
  - [Offset](#offset)
  - [Face](#face)
- [Fastener Specifications](#fastener-specifications)
  - [Dowel](#dowel)
  - [Screw](#screw)
- [DSL Module](#dsl-module)
- [Shell Module](#shell-module)
- [Complete Examples](#complete-examples)

## Overview

nichiyou-daiku follows a functional core, imperative shell architecture:

- **Core**: Pure data models and business logic
- **Shell**: External integrations (3D export, report generation)
- **DSL**: Domain-specific language parser

```
nichiyou_daiku/
├── core/           # Pure data models
│   ├── piece.py    # Lumber piece definitions
│   ├── anchor.py   # Connection point specifications
│   ├── connection.py # Connection definitions
│   ├── model.py    # Project model
│   ├── assembly/   # 3D assembly
│   ├── dowel.py    # Dowel specifications
│   ├── screw.py    # Screw specifications
│   └── geometry/   # Geometric primitives
├── dsl/            # DSL parser
└── shell/          # External integrations
```

## Core Module

### Piece

A lumber piece with specific type and length.

#### PieceType

Enumeration of supported lumber types.

```python
from nichiyou_daiku.core.piece import PieceType

class PieceType(Enum):
    PT_2x4 = "2x4"  # 89mm × 38mm cross-section
    PT_1x4 = "1x4"  # 89mm × 19mm cross-section
```

**Methods:**

| Method | Description |
|--------|-------------|
| `PieceType.of(value: str)` | Create from string (e.g., "2x4") |

**Example:**

```python
>>> PieceType.of("2x4")
<PieceType.PT_2x4: '2x4'>

>>> PieceType.of("1x4")
<PieceType.PT_1x4: '1x4'>
```

#### Piece

Represents a piece of lumber.

```python
from nichiyou_daiku.core.piece import Piece, PieceType

class Piece(BaseModel, frozen=True):
    id: str              # Unique identifier
    type: PieceType      # Lumber type
    length: float        # Length in millimeters
```

**Factory Methods:**

| Method | Description |
|--------|-------------|
| `Piece.of(piece_type, length, id_=None)` | Create a piece (auto-generates UUID if id_ not provided) |

**Example:**

```python
>>> piece = Piece.of(PieceType.PT_2x4, 1000.0, "leg-1")
>>> piece.id
'leg-1'
>>> piece.type
<PieceType.PT_2x4: '2x4'>
>>> piece.length
1000.0
```

#### get_shape

Get the dimensions of a piece or piece type.

```python
from nichiyou_daiku.core.piece import get_shape

# Overloaded function:
# - get_shape(PieceType) -> Shape2D (cross-section)
# - get_shape(Piece) -> Shape3D (includes length)
```

**Example:**

```python
>>> shape2d = get_shape(PieceType.PT_2x4)
>>> shape2d.width   # mm
89.0
>>> shape2d.height  # mm
38.0

>>> piece = Piece.of(PieceType.PT_2x4, 1000.0)
>>> shape3d = get_shape(piece)
>>> shape3d.width
89.0
>>> shape3d.height
38.0
>>> shape3d.length
1000.0
```

### Anchor

Specifies a connection point on a piece.

#### Anchor

Defines where a connection occurs on a piece face.

```python
from nichiyou_daiku.core.anchor import Anchor
from nichiyou_daiku.core.geometry import FromMin, FromMax

class Anchor(BaseModel, frozen=True):
    contact_face: Face        # Face that touches the other piece
    edge_shared_face: Face    # Face whose edge is shared
    offset: Offset            # Position along the shared edge
```

**Connection Model:**

Two pieces always connect by sharing an edge. The anchor defines:
1. `contact_face`: Which face touches the other piece
2. `edge_shared_face`: Which edge of the contact face is aligned
3. `offset`: Position along that edge

```
         edge_shared_face = "front"
                ↓
    ┌───────────┼───────────┐
    │           │           │
    │    contact_face       │  ← Piece A
    │       = "top"         │
    └───────────┴───────────┘
                │
    ┌───────────┴───────────┐
    │    contact_face       │
    │      = "down"         │  ← Piece B
    └───────────────────────┘
```

**Valid Face Combinations:**

The `contact_face` and `edge_shared_face` must be adjacent (not opposite):

| Valid | Invalid |
|-------|---------|
| top + front | top + down |
| left + back | left + right |
| down + left | front + back |

**Factory Methods:**

| Method | Description |
|--------|-------------|
| `Anchor.of(contact_face, edge_shared_face, offset)` | Create with validation |

**Example:**

```python
>>> anchor = Anchor(
...     contact_face="front",
...     edge_shared_face="top",
...     offset=FromMax(value=100)
... )
>>> anchor.contact_face
'front'
```

#### BoundAnchor

An anchor bound to a specific piece.

```python
from nichiyou_daiku.core.anchor import BoundAnchor

class BoundAnchor(BaseModel, frozen=True):
    piece: Piece    # The piece this anchor belongs to
    anchor: Anchor  # The anchor position
```

**Factory Methods:**

| Method | Description |
|--------|-------------|
| `BoundAnchor.of(piece, anchor)` | Create with offset validation |

**Example:**

```python
>>> piece = Piece.of(PieceType.PT_2x4, 1000.0, "leg-1")
>>> anchor = Anchor(
...     contact_face="front",
...     edge_shared_face="top",
...     offset=FromMax(value=100)
... )
>>> bound = BoundAnchor(piece=piece, anchor=anchor)
```

### Connection

Defines how two pieces connect.

#### Connection Types

```python
from nichiyou_daiku.core.connection import (
    VanillaConnection,
    DowelConnection,
    ScrewConnection,
    ConnectionType,
)

class VanillaConnection(BaseModel, frozen=True):
    """Basic connection without reinforcement."""
    pass

class DowelConnection(BaseModel, frozen=True):
    """Connection reinforced with dowels."""
    radius: float  # Dowel radius in mm
    depth: float   # Dowel depth in mm

class ScrewConnection(BaseModel, frozen=True):
    """Connection reinforced with screws."""
    diameter: float  # Screw diameter in mm
    length: float    # Screw length in mm

ConnectionType = VanillaConnection | DowelConnection | ScrewConnection
```

#### Connection

Complete connection specification between two pieces.

```python
from nichiyou_daiku.core.connection import Connection

class Connection(BaseModel, frozen=True):
    base: BoundAnchor           # Base piece (stays fixed)
    target: BoundAnchor         # Target piece (attaches to base)
    type: ConnectionType        # Connection type (default: VanillaConnection)
```

**Factory Methods:**

| Method | Description |
|--------|-------------|
| `Connection.of_vanilla(base, target)` | Create vanilla connection |
| `Connection.of_dowel(base, target, spec)` | Create dowel connection |
| `Connection.of_screw(base, target, spec)` | Create screw connection |

**Example:**

```python
>>> from nichiyou_daiku.core.dowel import Dowel, as_spec

>>> conn = Connection(
...     base=BoundAnchor(piece=piece1, anchor=anchor1),
...     target=BoundAnchor(piece=piece2, anchor=anchor2),
... )

# With dowel
>>> conn = Connection.of_dowel(
...     base=BoundAnchor(piece=piece1, anchor=anchor1),
...     target=BoundAnchor(piece=piece2, anchor=anchor2),
...     spec=as_spec(Dowel.D8_L30),
... )
```

### Model

Complete project model with pieces and connections.

```python
from nichiyou_daiku.core.model import Model

class Model(BaseModel, frozen=True):
    pieces: dict[str, Piece]                      # Piece ID -> Piece
    connections: dict[tuple[str, str], Connection] # (base_id, target_id) -> Connection
    label: str | None = None                       # Optional project label
```

**Factory Methods:**

| Method | Description |
|--------|-------------|
| `Model.of(pieces, connections, label=None)` | Create from iterables |

**Example:**

```python
>>> piece1 = Piece.of(PieceType.PT_2x4, 1000.0, "piece-1")
>>> piece2 = Piece.of(PieceType.PT_2x4, 800.0, "piece-2")
>>> conn = Connection(
...     base=BoundAnchor(piece=piece1, anchor=anchor1),
...     target=BoundAnchor(piece=piece2, anchor=anchor2),
... )
>>> model = Model.of(
...     pieces=[piece1, piece2],
...     connections=[conn],
...     label="My Table"
... )
>>> len(model.pieces)
2
>>> ("piece-1", "piece-2") in model.connections
True
```

### Assembly

3D assembly with joint positions and orientations.

```python
from nichiyou_daiku.core.assembly import Assembly

class Assembly(BaseModel, frozen=True):
    model: Model                              # Source model
    boxes: dict[str, Box]                     # Piece ID -> 3D bounding box
    joints: dict[str, Joint]                  # Joint ID -> Joint
    joint_conns: list[tuple[str, str]]        # Connected joint ID pairs
    pilot_holes: dict[str, list[tuple[Point3D, Hole]]]  # Piece ID -> holes
    label: str | None                         # Optional label
```

**Factory Methods:**

| Method | Description |
|--------|-------------|
| `Assembly.of(model)` | Create 3D assembly from model |

**Example:**

```python
>>> assembly = Assembly.of(model)
>>> len(assembly.joints)
2  # One joint pair creates 2 joints
>>> len(assembly.joint_conns)
1
```

## Geometry Module

### Offset

Position along an edge, measured from either end.

```python
from nichiyou_daiku.core.geometry import FromMin, FromMax, Offset

class FromMin(BaseModel, frozen=True):
    """Offset from minimum (start) position."""
    value: float  # Distance in mm

class FromMax(BaseModel, frozen=True):
    """Offset from maximum (end) position."""
    value: float  # Distance in mm

Offset = FromMin | FromMax
```

**Example:**

```python
>>> offset1 = FromMin(value=100)  # 100mm from start
>>> offset2 = FromMax(value=50)   # 50mm from end
```

### Face

Six faces of a rectangular piece.

```python
Face = Literal["top", "down", "left", "right", "front", "back"]
```

**Face Diagram:**

```
        top
         │
  left ──┼── right
         │
       down

  back ──┼── front
```

**Utility Functions:**

| Function | Description |
|----------|-------------|
| `opposite(face)` | Get opposite face |
| `cross(face1, face2)` | Get perpendicular face |
| `is_adjacent(face1, face2)` | Check if faces are adjacent |

## Fastener Specifications

### Dowel

Standard wooden dowel sizes.

```python
from nichiyou_daiku.core.dowel import Dowel, DowelSpec, as_spec

class DowelSpec(BaseModel, frozen=True):
    diameter: float  # mm
    length: float    # mm

class Dowel(Enum):
    D6_L25 = "6x25"
    D6_L30 = "6x30"
    D8_L25 = "8x25"
    D8_L30 = "8x30"
    D8_L40 = "8x40"
    D10_L30 = "10x30"
    D10_L40 = "10x40"
    D12_L40 = "12x40"
```

**Functions:**

| Function | Description |
|----------|-------------|
| `Dowel.of(value)` | Create from string (e.g., "8x30") |
| `as_spec(dowel)` | Convert preset to DowelSpec |

**Example:**

```python
>>> dowel = Dowel.of("8x30")
>>> spec = as_spec(dowel)
>>> spec.diameter
8.0
>>> spec.length
30.0
```

### Screw

Standard screw sizes including slim and coarse thread types.

```python
from nichiyou_daiku.core.screw import (
    ScrewSpec,
    SlimScrew,
    CoarseThreadScrew,
    as_spec,
)

class ScrewSpec(BaseModel, frozen=True):
    diameter: float  # mm
    length: float    # mm

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
```

**Functions:**

| Function | Description |
|----------|-------------|
| `SlimScrew.of(value)` | Create from string (e.g., "3.3x50") |
| `CoarseThreadScrew.of(value)` | Create from string (e.g., "3.8x57") |
| `as_spec(screw)` | Convert preset to ScrewSpec |

**Example:**

```python
>>> screw = SlimScrew.of("3.3x50")
>>> spec = as_spec(screw)
>>> spec.diameter
3.3
>>> spec.length
50.0
```

## DSL Module

Parse `.nd` files into Model objects.

```python
from nichiyou_daiku.dsl import (
    parse_dsl,
    DSLError,
    DSLSyntaxError,
    DSLSemanticError,
    DSLValidationError,
)
```

**Functions:**

| Function | Description |
|----------|-------------|
| `parse_dsl(source: str) -> Model` | Parse DSL string into Model |

**Exceptions:**

| Exception | Description |
|-----------|-------------|
| `DSLError` | Base exception for all DSL errors |
| `DSLSyntaxError` | Invalid syntax |
| `DSLSemanticError` | Invalid references (e.g., unknown piece) |
| `DSLValidationError` | Invalid values (e.g., unknown preset) |

**Example:**

```python
>>> dsl = """
... (leg:2x4 =720)
... (apron:2x4 =600)
... leg -[FR>100 DB<0]- apron
... """
>>> model = parse_dsl(dsl)
>>> len(model.pieces)
2
```

See [DSL Specification](./dsl-specification.md) for complete syntax reference.

## Shell Module

External integrations for 3D export and reports.

### Resource Extraction

```python
from nichiyou_daiku.shell import (
    extract_resources,
    ResourceSummary,
    PieceResource,
)

def extract_resources(assembly: Assembly) -> ResourceSummary:
    """Extract bill of materials from assembly."""
```

**Example:**

```python
>>> resources = extract_resources(assembly)
>>> resources.pretty_print()
```

### Report Generation

```python
from nichiyou_daiku.shell import generate_markdown_report

def generate_markdown_report(
    resources: ResourceSummary,
    project_name: str = "Woodworking Project",
    standard_lengths: dict[PieceType, list[float]] | None = None,
    include_cut_diagram: bool = True,
) -> str:
    """Generate markdown report with cut optimization."""
```

**Example:**

```python
>>> report = generate_markdown_report(
...     resources,
...     project_name="My Table",
...     include_cut_diagram=True,
... )
>>> print(report)
```

### 3D Export (Optional)

Requires `build123d` package.

```python
from nichiyou_daiku.shell import assembly_to_build123d

def assembly_to_build123d(
    assembly: Assembly,
    fillet_radius: float = 5.0,
) -> "Compound":
    """Convert assembly to build123d Compound for 3D visualization."""
```

**Example:**

```python
>>> compound = assembly_to_build123d(assembly, fillet_radius=2.0)
>>> # Use with ocp-vscode or export to STL/STEP
```

## Complete Examples

### Simple Table

```python
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.geometry import FromMin, FromMax

# Create pieces
leg1 = Piece.of(PieceType.PT_2x4, 720.0, "leg1")
leg2 = Piece.of(PieceType.PT_2x4, 720.0, "leg2")
apron = Piece.of(PieceType.PT_2x4, 600.0, "apron")

# Define connections
connections = [
    Connection(
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
        )
    ),
    Connection(
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
        )
    ),
]

# Create model and assembly
model = Model.of(
    pieces=[leg1, leg2, apron],
    connections=connections,
    label="Simple Table"
)
assembly = Assembly.of(model)
```

### Using DSL

```python
from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.core.assembly import Assembly

dsl = """
// Simple table with dowel joints
(leg1:2x4 =720)
(leg2:2x4 =720)
(apron:2x4 =600)

leg1 -[FR>100 DB<0 D(:8x30)]- apron
leg2 -[FL>100 DB>0 D(:8x30)]- apron
"""

model = parse_dsl(dsl)
assembly = Assembly.of(model)
```

### With Screw Connections

```python
from nichiyou_daiku.core.screw import SlimScrew, as_spec
from nichiyou_daiku.core.connection import Connection

conn = Connection.of_screw(
    base=BoundAnchor(piece=leg, anchor=leg_anchor),
    target=BoundAnchor(piece=apron, anchor=apron_anchor),
    spec=as_spec(SlimScrew.D3_3_L50),
)
```

Or using DSL:

```python
dsl = """
(leg:2x4 =720)
(apron:2x4 =600)

leg -[FR>100 FB<0 S(Slim:3.3x50)]- apron
"""
```
