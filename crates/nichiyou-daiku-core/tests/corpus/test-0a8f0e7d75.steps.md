# case: assembly steps

No steps block: each step adds one piece. Group pieces with a steps block, e.g. `steps { "Frame": a, b, ... }`.

## Parts

| Pieces | Lumber | Length (mm) | Count | Drawing |
|--------|--------|-------------|-------|---------|
| a | 2x4 | 500 | 1 |  |
| b, floating | 2x4 | 300 | 2 |  |

## Step 1

![Step 1](step-01.png)

| Piece | Lumber | Length (mm) |
|-------|--------|-------------|
| a | 2x4 | 500 |
| b | 2x4 | 300 |

## Step 2 (sub-assembly)

![Step 2](step-02.png)

| Piece | Lumber | Length (mm) |
|-------|--------|-------------|
| floating | 2x4 | 300 |
