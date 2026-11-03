"""Check a STEP the Rust CLI wrote (R5): every piece a valid solid, named
as the design names it, their volume the STL's.

    .venv/bin/python tools/check_step.py design.nd model.step model.stl
"""

import re
import struct
import sys
from pathlib import Path

from build123d import import_step

from nichiyou_daiku.dsl import parse_dsl

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def stl_volume(path: Path) -> float:
    data = path.read_bytes()
    (count,) = struct.unpack_from("<I", data, 80)
    total = 0.0
    for k in range(count):
        values = struct.unpack_from("<12f", data, 84 + 50 * k)
        a, b, c = values[3:6], values[6:9], values[9:12]
        cross = (
            b[1] * c[2] - b[2] * c[1],
            b[2] * c[0] - b[0] * c[2],
            b[0] * c[1] - b[1] * c[0],
        )
        total += (a[0] * cross[0] + a[1] * cross[1] + a[2] * cross[2]) / 6.0
    return total


def main(design: str, step: str, stl: str) -> int:
    pieces = list(parse_dsl(Path(design).read_text(encoding="utf-8")).pieces)
    shape = import_step(step)
    parts = list(shape.children)
    problems = []
    if len(parts) != len(pieces):
        problems.append(f"{len(parts)} parts for {len(pieces)} pieces")
    named = sorted(p for p in pieces if not UUID.match(p))
    labels = sorted(part.label for part in parts if not UUID.match(part.label))
    if named != labels:
        problems.append(f"names {labels} for pieces {named}")
    total = 0.0
    for part in parts:
        solids = part.solids()
        if len(solids) != 1 or not solids[0].is_valid:
            problems.append(
                f"{part.label}: {len(solids)} solids, valid: {[s.is_valid for s in solids]}"
            )
        total += sum(s.volume for s in solids)
    mesh = stl_volume(Path(stl))
    if abs(total - mesh) > 0.002 * mesh:
        problems.append(f"volume {total:.1f} in the STEP, {mesh:.1f} in the STL")
    for problem in problems:
        print(f"{step}: {problem}")
    print(f"{step}: {len(parts)} parts, volume {total:.1f} (STL {mesh:.1f})")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
