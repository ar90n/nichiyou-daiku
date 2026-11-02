# case: assembly steps

No steps block: each step adds one piece. Group pieces with a steps block, e.g. `steps { "Frame": frame1, frame2, ... }`.

## Parts

| Pieces | Lumber | Length (mm) | Count | Drawing |
|--------|--------|-------------|-------|---------|
| frame1, frame2 | 2x4 | 1000 | 2 |  |
| panel1, panel2 | 1x4 | 500 | 2 |  |

## Step 1

![Step 1](step-01.png)

| Piece | Lumber | Length (mm) |
|-------|--------|-------------|
| frame1 | 2x4 | 1000 |
| frame2 | 2x4 | 1000 |

## Step 2

![Step 2](step-02.png)

| Piece | Lumber | Length (mm) |
|-------|--------|-------------|
| panel1 | 1x4 | 500 |

## Step 3 (sub-assembly)

![Step 3](step-03.png)

| Piece | Lumber | Length (mm) |
|-------|--------|-------------|
| panel2 | 1x4 | 500 |
