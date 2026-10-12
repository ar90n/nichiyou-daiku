# Fastener Presets Reference

Complete list of all available fastener presets in nichiyou-daiku.

## Dowel Presets

Wooden dowels for invisible joints. Standard sizes available in Japan.

| Preset | Diameter (mm) | Length (mm) | DSL Syntax |
|--------|---------------|-------------|------------|
| 6x25 | 6 | 25 | `D(:6x25)` |
| 6x30 | 6 | 30 | `D(:6x30)` |
| 8x25 | 8 | 25 | `D(:8x25)` |
| 8x30 | 8 | 30 | `D(:8x30)` |
| 8x40 | 8 | 40 | `D(:8x40)` |
| 10x30 | 10 | 30 | `D(:10x30)` |
| 10x40 | 10 | 40 | `D(:10x40)` |
| 12x40 | 12 | 40 | `D(:12x40)` |

**Python Usage:**
```python
from nichiyou_daiku.core.dowel import Dowel, as_spec

dowel = Dowel.of("8x30")
spec = as_spec(dowel)  # DowelSpec(diameter=8.0, length=30.0)
```

## Screw Presets

### Slim Screws (SlimScrew)

Thin screws less likely to split wood. No pilot hole typically needed.

| Preset | Diameter (mm) | Length (mm) | DSL Syntax |
|--------|---------------|-------------|------------|
| 3.3x25 | 3.3 | 25 | `S(Slim:3.3x25)` |
| 3.3x30 | 3.3 | 30 | `S(Slim:3.3x30)` |
| 3.3x35 | 3.3 | 35 | `S(Slim:3.3x35)` |
| 3.3x40 | 3.3 | 40 | `S(Slim:3.3x40)` |
| 3.3x45 | 3.3 | 45 | `S(Slim:3.3x45)` |
| 3.3x50 | 3.3 | 50 | `S(Slim:3.3x50)` |
| 3.8x55 | 3.8 | 55 | `S(Slim:3.8x55)` |
| 3.8x60 | 3.8 | 60 | `S(Slim:3.8x60)` |
| 3.8x65 | 3.8 | 65 | `S(Slim:3.8x65)` |
| 3.8x70 | 3.8 | 70 | `S(Slim:3.8x70)` |
| 3.8x75 | 3.8 | 75 | `S(Slim:3.8x75)` |
| 4.2x90 | 4.2 | 90 | `S(Slim:4.2x90)` |

**Python Usage:**
```python
from nichiyou_daiku.core.screw import SlimScrew, as_spec

screw = SlimScrew.of("3.3x50")
spec = as_spec(screw)  # ScrewSpec(diameter=3.3, length=50.0)
```

### Coarse Thread Screws (CoarseThreadScrew)

Heavy-duty screws with stronger holding power.

| Preset | Diameter (mm) | Length (mm) | DSL Syntax |
|--------|---------------|-------------|------------|
| 3.8x25 | 3.8 | 25 | `S(Coarse:3.8x25)` |
| 3.8x30 | 3.8 | 30 | `S(Coarse:3.8x30)` |
| 3.8x35 | 3.8 | 35 | `S(Coarse:3.8x35)` |
| 3.8x40 | 3.8 | 40 | `S(Coarse:3.8x40)` |
| 3.8x45 | 3.8 | 45 | `S(Coarse:3.8x45)` |
| 3.8x50 | 3.8 | 50 | `S(Coarse:3.8x50)` |
| 3.8x57 | 3.8 | 57 | `S(Coarse:3.8x57)` |
| 4.2x65 | 4.2 | 65 | `S(Coarse:4.2x65)` |
| 4.2x75 | 4.2 | 75 | `S(Coarse:4.2x75)` |
| 4.5x90 | 4.5 | 90 | `S(Coarse:4.5x90)` |
| 4.5x100 | 4.5 | 100 | `S(Coarse:4.5x100)` |
| 5.2x120 | 5.2 | 120 | `S(Coarse:5.2x120)` |

**Python Usage:**
```python
from nichiyou_daiku.core.screw import CoarseThreadScrew, as_spec

screw = CoarseThreadScrew.of("3.8x57")
spec = as_spec(screw)  # ScrewSpec(diameter=3.8, length=57.0)
```

## Screw Selection Guide

The screw is driven through the **target** (contacted on its front/back face) into the **base**. The library enforces:

- length > target thickness (38 for 2x lumber, 19 for 1x lumber)
- length < target thickness + base depth along its contact normal (front/back → thickness, left/right → width, top/down → piece length)

Recommended sizes when the base is also contacted on a wide (front/back) face:

| Target → Base | Allowed length | Recommended Screw |
|---------------|----------------|-------------------|
| 2x4 → 2x4 (38mm + 38mm) | 39-76mm | Slim 3.8x65, Coarse 3.8x57 |
| 1x4 → 2x4 (19mm + 38mm) | 20-57mm | Slim 3.3x45, Coarse 3.8x40 |
| 1x4 → 1x4 (19mm + 19mm) | 20-38mm | Slim 3.3x30, Coarse 3.8x30 |

When the base is contacted on its narrow face (as deep as its width) or its end (piece length deep), longer screws are allowed.

## Dowel Fit

A dowel of length L goes L/2 into each piece. L/2 must be less than each piece's depth along its contact normal, or the hole comes out on the far face (front/back → thickness, left/right → width, top/down → piece length). For example, every preset fits a 2x4 contacted on its front/back face (38mm), but `12x40` (20mm per piece) does not fit a 1x4 contacted on its front/back face (19mm).

## Custom Specifications

For non-preset dimensions, use numeric values in DSL. The dowel form is `D(radius, total length)`; the screw form is `S(diameter, length)`:

```nd
(post:2x4 =600)
(rail_high:2x4 =400)
(rail_low:2x4 =400)
post -[FL<300 BT<0 D(5, 30)]- rail_high   // Custom dowel: radius 5mm (10mm diameter), total length 30mm
post -[FL<100 BT<0 S(4, 60)]- rail_low    // Custom screw: diameter 4mm, length 60mm
```

Or in Python (`DowelConnection.depth` is the total dowel length):
```python
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.connection import Connection, DowelConnection, ScrewConnection
from nichiyou_daiku.core.geometry import FromMin

post = Piece.of(PieceType.PT_2x4, 600.0, "post")
rail = Piece.of(PieceType.PT_2x4, 400.0, "rail")
base = BoundAnchor(
    piece=post,
    anchor=Anchor(contact_face="front", edge_shared_face="left", offset=FromMin(value=300)),
)
target = BoundAnchor(
    piece=rail,
    anchor=Anchor(contact_face="back", edge_shared_face="top", offset=FromMin(value=0)),
)

dowel_conn = Connection(
    base=base,
    target=target,
    type=DowelConnection(radius=5.0, depth=30.0),
)

screw_conn = Connection(
    base=base,
    target=target,
    type=ScrewConnection(diameter=4.0, length=60.0),
)
```
