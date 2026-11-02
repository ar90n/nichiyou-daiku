# case: assembly steps

No steps block: each step adds one piece. Group pieces with a steps block, e.g. `steps { "Frame": beam1, beam2, ... }`.

## Parts

| Pieces | Lumber | Length (mm) | Count | Drawing |
|--------|--------|-------------|-------|---------|
| beam1 | 2x4 | 1000 | 1 |  |
| beam2 | 2x4 | 800 | 1 | [part-01.png](part-01.png) |
| beam3 | 2x4 | 600 | 1 | [part-02.png](part-02.png) |

### beam2

![Part 1](part-01.png)

### beam3

![Part 2](part-02.png)

## Step 1

![Step 1](step-01.png)

| Piece | Lumber | Length (mm) |
|-------|--------|-------------|
| beam1 | 2x4 | 1000 |
| beam2 | 2x4 | 800 |

## Step 2

![Step 2](step-02.png)

| Piece | Lumber | Length (mm) |
|-------|--------|-------------|
| beam3 | 2x4 | 600 |

| Fastener | Count |
|----------|-------|
| Dowel 10x25 | 2 |
