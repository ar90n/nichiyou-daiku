# case: assembly steps

No steps block: each step adds one piece. Group pieces with a steps block, e.g. `steps { "Frame": p1, p2, ... }`.

## Parts

| Pieces | Lumber | Length (mm) | Count | Drawing |
|--------|--------|-------------|-------|---------|
| p1 | 2x4 | 1000 | 1 |  |
| p2 | 2x4 | 1200 | 1 |  |
| p3 | 1x4 | 800 | 1 |  |
| p4 | 1x4 | 600 | 1 |  |

## Step 1

![Step 1](step-01.png)

| Piece | Lumber | Length (mm) |
|-------|--------|-------------|
| p1 | 2x4 | 1000 |
| p2 | 2x4 | 1200 |

## Step 2 (sub-assembly)

![Step 2](step-02.png)

| Piece | Lumber | Length (mm) |
|-------|--------|-------------|
| p3 | 1x4 | 800 |
| p4 | 1x4 | 600 |
