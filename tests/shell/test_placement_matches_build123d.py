"""Core placement must match the RigidJoint placement it replaces.

Temporary: removed once build123d renders the core placement.
"""

import itertools
import re
from pathlib import Path

import pytest

pytest.importorskip("build123d")

from nichiyou_daiku.core.anchor import Anchor, BoundAnchor  # noqa: E402
from nichiyou_daiku.core.assembly import Assembly  # noqa: E402
from nichiyou_daiku.core.connection import Connection  # noqa: E402
from nichiyou_daiku.core.geometry import FromMax, FromMin, is_adjacent  # noqa: E402
from nichiyou_daiku.core.model import Model  # noqa: E402
from nichiyou_daiku.core.piece import Piece, PieceType  # noqa: E402
from nichiyou_daiku.dsl import parse_dsl  # noqa: E402
from nichiyou_daiku.shell.build123d_export import assembly_to_build123d  # noqa: E402

ROOT = Path(__file__).parents[2]
FACES = ["top", "down", "left", "right", "front", "back"]
ADJACENT = [(c, e) for c in FACES for e in FACES if is_adjacent(c, e)]
DOCS = [
    "prompts/system.md",
    "prompts/reference/dsl-complete.md",
    "prompts/reference/python-api.md",
    "prompts/README.md",
    "docs/dsl-specification.md",
    "docs/dsl-specification_ja.md",
    "README.md",
]
ND_BLOCK = re.compile(r"`{3}nd\n(.*?)`{3}", re.S)


def _designs() -> list[tuple[str, str]]:
    designs = [
        (p.name, p.read_text())
        for p in sorted((ROOT / "examples/nd_files").glob("*.nd"))
    ]
    for doc in DOCS:
        blocks = ND_BLOCK.findall((ROOT / doc).read_text())
        designs += [(f"{doc}#{i}", b) for i, b in enumerate(blocks) if "-[" in b]
    return designs


def _assert_same_boxes(assembly: Assembly) -> None:
    compound = assembly_to_build123d(assembly, fillet_radius=0)
    for child in compound.children:
        bb = child.bounding_box()
        low, high = assembly.placement.poses[child.label].bounds(
            assembly.model.pieces[child.label]
        )
        assert (
            bb.min.X,
            bb.min.Y,
            bb.min.Z,
            bb.max.X,
            bb.max.Y,
            bb.max.Z,
        ) == pytest.approx((low.x, low.y, low.z, high.x, high.y, high.z), abs=1e-6), (
            child.label
        )


@pytest.mark.parametrize(
    "base_faces,target_faces,offsets",
    [
        (b, t, o)
        for b, t in itertools.product(ADJACENT, ADJACENT)
        for o in (
            (FromMin(value=10), FromMin(value=5)),
            (FromMax(value=10), FromMax(value=0)),
        )
    ],
)
def test_two_piece_placement_matches(base_faces, target_faces, offsets):
    a = Piece.of(PieceType.PT_2x4, 500.0, "a")
    b = Piece.of(PieceType.PT_2x4, 300.0, "b")
    connection = Connection(
        base=BoundAnchor(
            piece=a,
            anchor=Anchor(
                contact_face=base_faces[0],
                edge_shared_face=base_faces[1],
                offset=offsets[0],
            ),
        ),
        target=BoundAnchor(
            piece=b,
            anchor=Anchor(
                contact_face=target_faces[0],
                edge_shared_face=target_faces[1],
                offset=offsets[1],
            ),
        ),
    )
    _assert_same_boxes(Assembly.of(Model.of(pieces=[a, b], connections=[connection])))


@pytest.mark.parametrize("name,source", _designs(), ids=[n for n, _ in _designs()])
def test_design_placement_matches(name, source):
    assembly = Assembly.of(parse_dsl(source))
    if assembly.placement.conflicts or len(assembly.placement.groups) > 1:
        pytest.skip("RigidJoint placement is undefined for inconsistent models")
    _assert_same_boxes(assembly)
