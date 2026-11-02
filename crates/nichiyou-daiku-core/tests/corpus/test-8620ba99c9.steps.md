# case: assembly steps

No steps block: each step adds one piece. Group pieces with a steps block, e.g. `steps { "Frame": leg1, apron_front, ... }`.

## Parts

| Pieces | Lumber | Length (mm) | Count | Drawing |
|--------|--------|-------------|-------|---------|
| leg1, leg2, leg3, leg4 | 2x4 | 720 | 4 |  |
| apron_front, apron_back | 2x4 | 600 | 2 |  |

## Step 1

![Step 1](step-01.png)

| Piece | Lumber | Length (mm) |
|-------|--------|-------------|
| leg1 | 2x4 | 720 |
| apron_front | 2x4 | 600 |

## Step 2

![Step 2](step-02.png)

| Piece | Lumber | Length (mm) |
|-------|--------|-------------|
| leg2 | 2x4 | 720 |

## Step 3 (sub-assembly)

![Step 3](step-03.png)

| Piece | Lumber | Length (mm) |
|-------|--------|-------------|
| leg3 | 2x4 | 720 |
| apron_back | 2x4 | 600 |

## Step 4

![Step 4](step-04.png)

| Piece | Lumber | Length (mm) |
|-------|--------|-------------|
| leg4 | 2x4 | 720 |
