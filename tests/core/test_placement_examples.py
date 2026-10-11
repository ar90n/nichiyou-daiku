"""Example furniture keeps the placement it had before placement moved to core."""

import json
from pathlib import Path

import pytest

from nichiyou_daiku.core.placement import solve_placement
from nichiyou_daiku.dsl import parse_dsl

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "placement_examples.json").read_text()
)
EXAMPLES = Path(__file__).parents[2] / "examples" / "nd_files"


@pytest.mark.parametrize("name", sorted(FIXTURE))
def test_example_keeps_its_placement(name):
    model = parse_dsl((EXAMPLES / name).read_text())
    placement = solve_placement(model)
    assert placement.conflicts == ()
    for piece_id, (low, high) in FIXTURE[name].items():
        got_low, got_high = placement.poses[piece_id].bounds(model.pieces[piece_id])
        assert (
            got_low.x,
            got_low.y,
            got_low.z,
            got_high.x,
            got_high.y,
            got_high.z,
        ) == pytest.approx((*low, *high), abs=1e-6), piece_id


MIXED_LUMBER = """
(leg_1:2x4 =450)
(leg_2:2x4 =450)
(apron:2x4 =400)
(top_1:1x4 =500)
(top_2:1x4 =500)
leg_1 -[LB>0 DB>0]- apron
leg_2 -[RF>0 TF>0]- apron
leg_1 -[TF<0 BD<0]- top_1
leg_1 -[TF<0 BD<89]- top_2
"""

# Boxes from the RigidJoint placement before placement moved to core (237660d)
MIXED_LUMBER_BOXES = {
    "leg_1": (0.0, 0.0, 0.0, 89.0, 38.0, 450.0),
    "leg_2": (-489.0, 0.0, 0.0, -400.0, 38.0, 450.0),
    "apron": (-400.0, 0.0, 361.0, 0.0, 38.0, 450.0),
    "top_1": (0.0, -462.0, 450.0, 89.0, 38.0, 469.0),
    "top_2": (-89.0, -462.0, 450.0, 0.0, 38.0, 469.0),
}


def test_mixed_2x4_and_1x4_keeps_its_placement():
    model = parse_dsl(MIXED_LUMBER)
    placement = solve_placement(model)
    assert placement.conflicts == ()
    for piece_id, expected in MIXED_LUMBER_BOXES.items():
        low, high = placement.poses[piece_id].bounds(model.pieces[piece_id])
        assert (low.x, low.y, low.z, high.x, high.y, high.z) == pytest.approx(
            expected, abs=1e-6
        )
