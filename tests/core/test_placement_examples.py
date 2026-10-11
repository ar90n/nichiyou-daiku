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
