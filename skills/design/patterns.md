# Design Patterns

Verified layouts, length formulas and rules for writing `.nd` files. The DSL specification defines every construct used here.

## Verified Patterns (Follow These Exactly)

Every pattern below was built and checked: correct overall size, no overlapping pieces, all joints consistent.

### Basic Joints (2x4 pieces `a` and `b`)

| Joint | DSL | Result |
|-------|-----|--------|
| End to end | `a -[TF<0 DF<0]- b` | `b` continues `a` straight on from `a`'s top end |
| Corner (L) | `a -[TF<0 BD<0]- b` | `b` lies across `a`'s top end (b's back face down), b's down end flush with a's front face |
| T (butt) | `a -[FL<200 DF<0]- b` | `b`'s end butts against `a`'s front face, point 200mm above a's down end |

### Four-Legged Table (complete example)

Legs stand upright with their wide front faces toward the front of the table, so each leg shows **89mm to the front** and **38mm to the sides**. All aprons stand 89mm tall, sit between the legs, and are flush with the leg tops. Top boards run front to back (length = D) and lie flat on the leg tops and on `apron_front`: the two outer boards sit on the legs, the inner boards on `apron_front`.

```
Top view (front at the bottom):

  leg_bl ══ apron_back ══ leg_br
    ║                       ║
apron_left             apron_right
    ║                       ║
  leg_fl ══ apron_front ═ leg_fr
```

```nd
// Four-Legged Table
// Width: 800mm, Depth: 500mm, Height: 720mm
// 2x4 frame with 8x30 dowels, 1x4 top boards screwed down with Slim 3.3x45

// Legs: 720 - 19 (1x4 top) = 701
(leg_fl:2x4 =701)
(leg_fr:2x4 =701)
(leg_bl:2x4 =701)
(leg_br:2x4 =701)

// Front/back aprons: 800 - 2x89 = 622
(apron_front:2x4 =622)
(apron_back:2x4 =622)
// Side aprons: 500 - 2x38 = 424
(apron_left:2x4 =424)
(apron_right:2x4 =424)

// Top boards: 8 x 89 = 712, gap (800 - 712) / 7 = 12.57
(top_1:1x4 =500)
(top_2:1x4 =500)
(top_3:1x4 =500)
(top_4:1x4 =500)
(top_5:1x4 =500)
(top_6:1x4 =500)
(top_7:1x4 =500)
(top_8:1x4 =500)

// Front/back aprons: end into the legs' narrow faces, flush with the legs' front faces
leg_fl -[LB>0 DB>0 D(:8x30)]- apron_front
leg_fr -[RF>0 TF>0 D(:8x30)]- apron_front
leg_bl -[LB>0 DB>0 D(:8x30)]- apron_back
leg_br -[RF>0 TF>0 D(:8x30)]- apron_back

// Side aprons: end into the legs' wide faces, flush with the legs' outer sides
leg_fl -[BR>0 DB>0 D(:8x30)]- apron_left
leg_bl -[FR>0 TB>0 D(:8x30)]- apron_left
leg_fr -[BL>0 DF>0 D(:8x30)]- apron_right
leg_br -[FL>0 TF>0 D(:8x30)]- apron_right

// Top boards (screwed down through the board)
leg_fl -[TF<0 BD<0 S(Slim:3.3x45)]- top_1
apron_front -[RF<12.6 BT<0 S(Slim:3.3x45)]- top_2
apron_front -[RF<114.1 BT<0 S(Slim:3.3x45)]- top_3
apron_front -[RF<215.7 BT<0 S(Slim:3.3x45)]- top_4
apron_front -[RF<317.3 BT<0 S(Slim:3.3x45)]- top_5
apron_front -[RF<418.9 BT<0 S(Slim:3.3x45)]- top_6
apron_front -[RF<520.4 BT<0 S(Slim:3.3x45)]- top_7
leg_fr -[TF<0 BD<0 S(Slim:3.3x45)]- top_8
```

**Key insights**:
- The two legs of one apron use DIFFERENT anchors (`LB` + `DB` on one end, `RF` + `TF` on the other), because they touch the apron's two different ends.
- `>0` on the leg puts the point at the leg's top; `DB>0` / `TF>0` / `TB>0` / `DF>0` on the apron make its 89mm height hang below that point, flush with the leg tops.

Top boards over width W (1x4 boards on 2x4 legs, both 89mm wide):
- Number of boards: n = the largest n with n x 89 <= W
- Gap: g = (W - n x 89) / (n - 1)
- Offset of inner board k (k = 2 .. n-1): o_k = (k - 1) x (89 + g) - 89, measured from the apron_front end at leg_fl
- Example W=800: n=8, g=12.57, offsets 12.6, 114.1, 215.7, 317.3, 418.9, 520.4

### Lower Aprons (for a lower shelf)

Use the same 8 leg-to-apron connections as the upper aprons, replacing `>0` on the **leg** anchor with `>offset` (apron anchors unchanged). The apron hangs 89mm below the point, so for a lower apron whose **bottom edge** is h above the floor:

```
offset = leg_length - h - 89
Example: leg 800, bottom edge 150 above the floor → offset = 800 - 150 - 89 = 561 (apron occupies 150..239)
```

```text
leg_fl -[LB>561 DB>0]- lower_front     // ... and likewise for the other 7 lower-apron connections
// Shelf boards (1x4, length D) rest on lower_front, between the legs:
// offsets must stay within 0 .. 622 - 89 = 533
lower_front -[RF<12.6 BT<0]- shelf_1
lower_front -[RF<114.1 BT<0]- shelf_2
```

Unlike the top, the lower shelf cannot use boards over the legs (the legs continue upward), so all shelf boards sit between the legs. With A = lower_front length (W - 2 x 89, here 622): n = the largest n with n x 89 <= A, gap g = (A - n x 89) / (n + 1), offset of board k (k = 1 .. n): o_k = g + (k - 1) x (89 + g). Example A=622: n=6, offsets 12.6, 114.1, 215.7, 317.3, 418.9, 520.4.

### Shelf Unit: Side Posts and Shelves (screws)

Two upright 2x4 side posts; each shelf's ends butt against the posts' wide faces. The screw goes through the post (target, contact `B`/`F`) into the shelf end (base).

```nd
// Two-tier shelf: width 600 + 2x38 = 676, depth 89, height 800
(side_l:2x4 =800)
(side_r:2x4 =800)
(shelf_bottom:2x4 =600)
(shelf_top:2x4 =600)

// Shelf underside 100 above the floor
shelf_bottom -[DL<0 BL<100 S(Slim:3.8x65)]- side_l
shelf_bottom -[TL<0 FL<100 S(Slim:3.8x65)]- side_r
// Shelf flush with the post tops: point 38 below the top
shelf_top -[DL<0 BL>38 S(Slim:3.8x65)]- side_l
shelf_top -[TL<0 FL>38 S(Slim:3.8x65)]- side_r
```

- `BL<h` / `FL<h` on the post puts the shelf's underside h above the floor; `BL>t` / `FL>t` puts its underside t below the post top.
- The same layout with dowels: `side_l -[BL<300 DL<0 D(:8x30)]- shelf` and `side_r -[FL<300 TL<0 D(:8x30)]- shelf`.

---

## Length Calculation Rules

Account for the lumber dimensions at every joint. For the verified table pattern (legs show 89mm to the front, 38mm to the sides):

| Part | Formula | Example (W=800, D=500, H=720, 1x4 top) |
|------|---------|----------------------------------------|
| Legs | H - top thickness (19 for 1x boards, 38 for 2x boards) | 720 - 19 = 701 |
| Front/back aprons | W - 2 x 89 | 800 - 178 = 622 |
| Side aprons | D - 2 x 38 | 500 - 76 = 424 |
| Top boards | D | 500 |
| Lower apron leg offset | leg length - h - 89 (h = apron bottom above floor) | 701 - 150 - 89 = 462 |

For the shelf unit: width = shelf length + 2 x 38, depth = 89, height = post length.

---

## Generation Rules

### 1. Naming Conventions

| Component | Pattern | Example |
|-----------|---------|---------|
| Legs | `leg_{position}` | `leg_fl` (front-left) |
| Aprons | `apron_{direction}` | `apron_front` |
| Top boards | `top_{n}` | `top_1`, `top_2` |
| Shelves | `shelf_{n}` | `shelf_1` |

Position codes: `fl` (front-left), `fr` (front-right), `bl` (back-left), `br` (back-right)

Name the overall sizes as variables (`WIDTH = 800`) and derive lengths and offsets from them instead of writing hand-computed numbers; use descriptive names (`DEPTH`, not `D`). Leave a length unknown (`=?`) when the pieces at its two ends already fix it.

### 2. Connection Order

1. Leg-to-apron connections (frame structure)
2. Apron-to-apron connections (if any cross braces)
3. Top surface connections
4. Shelf connections

### 3. Comments

Always include:
- Project name and overall dimensions at the top
- Section comments grouping related pieces
- Length calculation notes where non-obvious

### 4. Validation Checklist (common mistakes)

Before running `validate`:
- [ ] All piece IDs are unique and defined before use
- [ ] At most one connection per base/target pair
- [ ] Face pairs are adjacent: no same (`FF`) or opposite (`TD`, `LR`, `FB`) faces; `B` is back, the bottom end is `D` (down)
- [ ] Every offset fits its edge (the width W across the width, the thickness T across the thickness, piece length along the length): `TL<50` and `TF<100` are errors
- [ ] Offset direction: `<` from the down end / left side / back side, `>` from the top end / right side / front side
- [ ] Screw targets use `front`/`back` contact faces; target thickness < screw length < base depth + target thickness
- [ ] Dowel half-length fits both pieces along their contact normals
- [ ] Fastener presets exist
- [ ] Lengths match the formulas above (e.g. front/back aprons W - 2x89, side aprons D - 2x38)
