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
    PT_1x4 = "1x4"  # 89mm (width) × 19mm (thickness) cross-section
    PT_1x6 = "1x6"  # 140mm (width) × 19mm (thickness) cross-section
    PT_1x8 = "1x8"  # 184mm (width) × 19mm (thickness) cross-section
    PT_2x2 = "2x2"  # 38mm (width) × 38mm (thickness) cross-section
    PT_2x4 = "2x4"  # 89mm (width) × 38mm (thickness) cross-section
    PT_2x6 = "2x6"  # 140mm (width) × 38mm (thickness) cross-section
```

**Methods:**

| Method | Description |
|--------|-------------|
| `PieceType.of(value: str)` | Create from string (e.g., "2x4") |

**Example:**

```python
>>> from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
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
    length: float | None  # Length in millimeters (> 0), or None: fixed by the connections (see Unknowns)
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

Each piece has its own local frame: X = width (`width`), Y = thickness (`height`), Z = length (`length`).

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
    offset: Offset | None     # Position along the shared edge, or None: the pieces may slide along it
```

**Connection Model:**

Two pieces always connect by sharing an edge. The anchor defines:
1. `contact_face`: Which face touches the other piece
2. `edge_shared_face`: An adjacent face; the anchor lies on the edge where the two faces meet
3. `offset`: Position along that edge

The edge runs along the axis perpendicular to both faces:

| Face pair (either order) | Edge runs along | Edge length | `FromMin(v)` measured from | `FromMax(v)` measured from |
|--------------------------|-----------------|-------------|----------------------------|----------------------------|
| top/down + front/back | width (X) | W | left side | right side |
| top/down + left/right | thickness (Y) | T | back side | front side |
| front/back + left/right | length (Z) | L | down end | top end |

`BoundAnchor` raises `ValueError` if the offset exceeds the edge length.

**Placement:** a connection places the target against the base so that (1) the two contact faces touch face to face, (2) the two edge_shared faces lie in one plane and face the same way, and (3) the two anchor points coincide. With `FromMin` on the target its min end/side (down/left/back) sits on the point; with `FromMax` its max end/side (top/right/front) does.

Example (2x4 leg L=700 standing on the floor z=0, 2x4 apron L=500): base anchor `front`/`left`/`FromMin(100)` on the leg and target anchor `down`/`front`/`FromMin(0)` on the apron (DSL `leg -[FL<100 DF<0]- apron`) put the apron's down end on the leg's front face, the apron's front face flush with the leg's left face, and the apron's left side on the point 100mm above the floor, so the apron occupies z=11..100. With `FromMax(0)` on the apron it occupies z=100..189.

**Valid Face Combinations:**

The `contact_face` and `edge_shared_face` must be adjacent (not the same, not opposite):

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
>>> from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
>>> from nichiyou_daiku.core.geometry import FromMin, FromMax
>>> anchor = Anchor(
...     contact_face="front",
...     edge_shared_face="top",
...     offset=FromMax(value=50)
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
...     offset=FromMax(value=50)  # front/top edge runs across the 89mm width
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
    depth: float   # Total dowel length in mm (half goes into each piece)

class ScrewConnection(BaseModel, frozen=True):
    """Connection reinforced with screws."""
    diameter: float  # Screw diameter in mm
    length: float    # Screw length in mm
    screw_type: Literal["slim", "coarse"] | None = None  # None when given by size alone

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

**Validation** (raises `ValueError`): a piece cannot connect to itself. Dowel: half the dowel length must be shorter than each piece's depth along its contact normal (front/back → thickness, left/right → width, top/down → piece length), so the hole stays blind. Screw: the target's contact face must be `front` or `back`, and target thickness < length < base depth along its contact normal + target thickness.

**Example:**

```python
>>> from nichiyou_daiku.core.connection import Connection
>>> from nichiyou_daiku.core.dowel import Dowel, as_spec
>>> leg = Piece.of(PieceType.PT_2x4, 720.0, "leg")
>>> apron = Piece.of(PieceType.PT_2x4, 600.0, "apron")
>>> leg_anchor = Anchor(contact_face="left", edge_shared_face="back", offset=FromMax(value=0))
>>> apron_anchor = Anchor(contact_face="down", edge_shared_face="back", offset=FromMax(value=0))

>>> conn = Connection(
...     base=BoundAnchor(piece=leg, anchor=leg_anchor),
...     target=BoundAnchor(piece=apron, anchor=apron_anchor),
... )

# With dowel
>>> dowel_conn = Connection.of_dowel(
...     base=BoundAnchor(piece=leg, anchor=leg_anchor),
...     target=BoundAnchor(piece=apron, anchor=apron_anchor),
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

`Model.of` raises `ValueError` for duplicate piece IDs, connections that reference pieces not in `pieces`, and a second connection for the same (base, target) pair.

**Example:**

```python
>>> from nichiyou_daiku.core.model import Model
>>> model = Model.of(
...     pieces=[leg, apron],
...     connections=[conn],
...     label="My Table"
... )
>>> len(model.pieces)
2
>>> ("leg", "apron") in model.connections
True
```

### Assembly

3D assembly: piece placement, fasteners (dowels and screws) and pilot holes.

```python
from nichiyou_daiku.core.assembly import Assembly

class Assembly(BaseModel, frozen=True):
    model: Model                              # Source model
    boxes: dict[str, Box]                     # Piece ID -> 3D bounding box
    fasteners: tuple[Fastener, ...]           # Dowels and screws, laid out in each contact area
    fastener_issues: tuple[LayoutIssue, ...]  # Connections whose fasteners do not fit or whose holes collide
    pilot_holes: dict[str, list[tuple[SurfacePoint, Hole]]]  # Piece ID -> holes (SurfacePoint names the drilled face)
    placement: Placement                      # World placement of every piece
    label: str | None                         # Optional label
```

**Factory Methods:**

| Method | Description |
|--------|-------------|
| `Assembly.of(model)` | Create 3D assembly from model |

**Example:**

```python
>>> from nichiyou_daiku.core.assembly import Assembly
>>> assembly = Assembly.of(model)
>>> len(assembly.fasteners)  # a vanilla connection has no fasteners
0
```

**Pilot holes:** a dowel connection adds a hole of the dowel diameter, length/2 deep, to each piece; a screw connection adds a through-hole to the target and a hole (length - target thickness) deep to the base; vanilla connections add none.

**Fasteners:** dowels and screws are laid out inside the rectangle where the two contact faces overlap: across the middle of its short side, and at 1/4 and 3/4 of its long side (one in the middle when the long side is shorter than 4 × diameter). A contact area narrower than 2 × diameter, or pieces that only touch along an edge, give a `LayoutIssue` instead of fasteners; `validate` reports it and other commands warn and carry on. Connections that contradict the placement get no fasteners either: their holes would never meet. When holes of two connections run into each other inside a piece, the later connection gets a `LayoutIssue` and both keep their fasteners. That issue also names the piece (`piece_id`), the earlier connection (`other`) and the two holes (`holes`: this connection's first, each as the `SurfacePoint` where it enters the piece and its `Hole`).

```python
class Fastener(BaseModel, frozen=True):
    base_id: str
    target_id: str
    kind: Literal["dowel", "screw"]
    base_position: SurfacePoint    # on the base's contact face
    target_position: SurfacePoint  # on the target's contact face
    base_hole: Hole
    target_hole: Hole

class LayoutIssue(BaseModel, frozen=True):
    base_id: str
    target_id: str
    kind: Literal["dowel", "screw"]
    message: str
```

### Placement

World position of every piece, solved from all connections at once (`Assembly.placement`). Rotations are exact multiples of 90°, and positions are solved per world axis, so every consistent constraint holds exactly. A constraint that contradicts the ones declared before it is reported in `conflicts` instead of being averaged in.

```python
from nichiyou_daiku.core.placement import (
    Conflict, Overlap, Placement, Pose,
    find_overlaps, overall_bounds, solve_placement,
)

class Pose(BaseModel, frozen=True):
    rotation: tuple[tuple[int, int, int], ...]  # signed permutation matrix, det +1
    translation: tuple[float, float, float]     # mm; local point p -> rotation @ p + translation
    # apply(point) -> Point3D, bounds(piece) -> (low, high) world box

class Conflict(BaseModel, frozen=True):
    base_id: str
    target_id: str
    kind: Literal["rotation", "contact", "flush", "edge"]
    axis: Literal["x", "y", "z"] | None         # None for rotation
    mismatch_mm: float | None                   # None for rotation
    loop: tuple[str, ...]                       # pieces from base to target the constraint would close

class Placement(BaseModel, frozen=True):
    poses: dict[str, Pose]
    groups: tuple[tuple[str, ...], ...]         # connected pieces; later groups are laid out along +X
    conflicts: tuple[Conflict, ...]
```

| Function | Description |
|--------|-------------|
| `solve_placement(model)` | Solve the placement (the same value as `Assembly.of(model).placement`); the model must have no unknowns |
| `find_overlaps(model, placement)` | Pairs of pieces whose boxes share volume (holes and fillets ignored) |
| `overall_bounds(model, placement)` | Smallest world box containing every piece |

**Example:**

```python
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.placement import find_overlaps
from nichiyou_daiku.dsl import parse_dsl

model = parse_dsl("(a:2x4 =500)\n(b:2x4 =300)\na -[FL<100 DF<0]- b\n")
assembly = Assembly.of(model)
print(assembly.placement.poses["b"].bounds(model.pieces["b"]))
print(assembly.placement.conflicts, find_overlaps(model, assembly.placement))
```

### Unknowns

A piece's length and a connection's offsets may be left unknown (`None`; `?` in the DSL) for the connections to fix. An unknown offset makes a sliding connection: the pieces touch and their edge-shared faces are flush, but they may slide along the shared edge, so another connection must fix where they sit. Both anchors of a connection have unknown offsets, or neither.

```python
from nichiyou_daiku.core.resolve import ResolutionError, resolve_model

def resolve_model(model: Model) -> Model:
    """The model with every unknown length and offset fixed by the connections."""

class ResolutionError(ValueError):
    piece_id: str | None                    # the piece whose length or position is open
    connection: tuple[str, str] | None      # the sliding connection whose edges do not meet
```

- `parse_dsl` and `Assembly.of` resolve automatically; `model.has_unknowns` tells whether a model still has unknowns.
- Resolving fails when a length or position is not fixed, a length would be 0 or negative, or two sliding pieces do not overlap along their edge.
- A sliding connection's offsets are set where the two edges start to overlap (the smallest base offset).
- `get_shape(piece)` and `solve_placement(model)` need a resolved model.

## Geometry Module

### Offset

Position along an edge, measured from either end.

```python
from nichiyou_daiku.core.geometry import FromMin, FromMax, Offset

class FromMin(BaseModel, frozen=True):
    """Offset from the min end of the edge (down end / left side / back side)."""
    value: float  # Distance in mm, >= 0

class FromMax(BaseModel, frozen=True):
    """Offset from the max end of the edge (top end / right side / front side)."""
    value: float  # Distance in mm, >= 0

Offset = FromMin | FromMax
```

**Example:**

```python
>>> offset1 = FromMin(value=100)  # 100mm from the min end
>>> offset2 = FromMax(value=50)   # 50mm from the max end
```

### Face

Six faces of a rectangular piece.

```python
from typing import Literal

Face = Literal["top", "down", "left", "right", "front", "back"]
```

Faces are named in the piece's local frame (X = width, Y = thickness, Z = length):

| Face | Normal | Kind | Size (W = width, T = thickness; 2x4: 89 × 38) |
|------|--------|------|-----------------------------------------------|
| top | +Z | end face at the max end of the length | W × T |
| down | -Z | end face at the min end of the length | W × T |
| front | +Y | wide face | W × length |
| back | -Y | wide face | W × length |
| right | +X | narrow face | T × length |
| left | -X | narrow face | T × length |

**Face Diagram** (cross-section, looking at the top end; top = +Z points at you):

```
                 front (+Y)
            ┌──────────────────┐
  left (-X) │                  │ right (+X)
            └──────────────────┘
                 back (-Y)
            ←─────── W ────────→
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
>>> from nichiyou_daiku.core.dowel import Dowel, as_spec
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
>>> from nichiyou_daiku.core.screw import SlimScrew, as_spec
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
>>> from nichiyou_daiku.dsl import parse_dsl
>>> dsl = """
... (leg:2x4 =720)
... (apron:2x4 =600)
... leg -[LB>0 DB>0]- apron
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
    HardwareItem,
    DrillBit,
)

def extract_resources(assembly: Assembly) -> ResourceSummary:
    """Extract bill of materials from assembly."""
```

**Example:**

```python
>>> from nichiyou_daiku.shell import extract_resources
>>> assembly = Assembly.of(model)
>>> resources = extract_resources(assembly)  # takes an Assembly, not a Model
>>> resources.total_pieces
2
>>> summary_text = resources.pretty_print()  # human-readable summary
```

`hardware` lists the dowels and screws to buy by kind and size (`HardwareItem`: `name`, `count`; screw presets keep `slim` or `coarse` in `ScrewConnection.screw_type`, a screw given by size alone is just "Screw"), and `drill_bits` the hole diameters with the number of holes and the deepest one (`DrillBit`; `deepest` is None when a hole goes through its piece):

```python
>>> from nichiyou_daiku.dsl import parse_dsl
>>> doweled = Assembly.of(parse_dsl("(a:2x4 =500)\n(b:2x4 =300)\na -[FL<100 DF<0 D(:8x30)]- b\n"))
>>> [(item.name, item.count) for item in extract_resources(doweled).hardware]
[('Dowel 8x30', 2)]
>>> [(bit.diameter, bit.holes, bit.deepest) for bit in extract_resources(doweled).drill_bits]
[(8.0, 4, 15.0)]
```

### Report Generation

```python
from nichiyou_daiku.shell import generate_markdown_report

def generate_markdown_report(
    resource_summary: ResourceSummary,
    project_name: str = "Woodworking Project",
    standard_lengths: dict[PieceType, list[float]] | None = None,
    include_cut_diagram: bool = True,
    include_anchor_details: bool = True,
    include_pilot_holes: bool = True,
) -> str:
    """Generate markdown report with cut optimization."""
```

The shopping list covers the lumber, the hardware and the drill bits. The cut plan allows a 3mm saw kerf per cut and warns about pieces longer than any stock board. Problems with the design (`ResourceSummary.issues`: contradicting connections, unconnected pieces, fasteners that do not fit, colliding holes) are listed in a Warnings section right after the overview. The cut plan itself comes from `nichiyou_daiku.shell.cutting.plan_cuts`, which returns a `LumberPlan` per lumber type; `CutPlan`, `DEFAULT_STANDARD_LENGTHS` and `DEFAULT_KERF_MM` live in the same module.

**Example:**

```python
>>> from nichiyou_daiku.shell import generate_markdown_report
>>> report = generate_markdown_report(
...     resources,
...     project_name="My Table",
...     include_cut_diagram=True,
... )
>>> report.splitlines()[0]
'# My Table Report'
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
>>> from nichiyou_daiku.shell import assembly_to_build123d
>>> compound = assembly_to_build123d(assembly, fillet_radius=2.0)
>>> # Use with ocp-vscode or export to STL/STEP
```

## Complete Examples

### Simple Frame

Two legs and an apron between them, flush with the leg tops.

```python
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.geometry import FromMax

# Create pieces
leg1 = Piece.of(PieceType.PT_2x4, 720.0, "leg1")
leg2 = Piece.of(PieceType.PT_2x4, 720.0, "leg2")
apron = Piece.of(PieceType.PT_2x4, 600.0, "apron")

# Define connections
connections = [
    # leg1 -[LB>0 DB>0]- apron
    Connection(
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
        )
    ),
    # leg2 -[RF>0 TF>0]- apron
    Connection(
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
        )
    ),
]

# Create model and assembly (overall 778 × 38 × 720mm)
model = Model.of(
    pieces=[leg1, leg2, apron],
    connections=connections,
    label="Simple Frame"
)
assembly = Assembly.of(model)
```

### Using DSL

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

### With Screw Connections

The screw goes through the target (contact face `front` or `back`) into the base.

```python
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.geometry import FromMin
from nichiyou_daiku.core.screw import SlimScrew, as_spec

post = Piece.of(PieceType.PT_2x4, 600.0, "post")
rail = Piece.of(PieceType.PT_2x4, 400.0, "rail")

# Rail screwed across the post's front face, 300mm above the post's down end
conn = Connection.of_screw(
    base=BoundAnchor(
        piece=post,
        anchor=Anchor(contact_face="front", edge_shared_face="left", offset=FromMin(value=300)),
    ),
    target=BoundAnchor(
        piece=rail,
        anchor=Anchor(contact_face="back", edge_shared_face="top", offset=FromMin(value=0)),
    ),
    spec=as_spec(SlimScrew.D3_3_L50),
)
```

Or using DSL:

```python
from nichiyou_daiku.dsl import parse_dsl

dsl = """
(post:2x4 =600)
(rail:2x4 =400)

post -[FL<300 BT<0 S(Slim:3.3x50)]- rail
"""
model = parse_dsl(dsl)
```
