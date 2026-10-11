"""Tests for solving piece placement from connections."""

from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from nichiyou_daiku.core.anchor import Anchor, BoundAnchor, as_point_3d
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.geometry import (
    Box,
    Edge,
    FromMax,
    FromMin,
    Point3D,
    Vector3D,
    edge_length_of,
    is_adjacent,
)
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
from nichiyou_daiku.core.placement import (
    Pose,
    find_overlaps,
    overall_bounds,
    relative_rotation,
    solve_placement,
)
from nichiyou_daiku.dsl import parse_dsl

FACES = ["top", "down", "left", "right", "front", "back"]
ADJACENT = [(c, e) for c in FACES for e in FACES if is_adjacent(c, e)]


def _vec(face) -> np.ndarray:
    v = Vector3D.normal_of(face)
    return np.array([v.x, v.y, v.z])


def _bound(piece: Piece, contact, edge) -> BoundAnchor:
    return BoundAnchor(
        piece=piece,
        anchor=Anchor(
            contact_face=contact, edge_shared_face=edge, offset=FromMin(value=0)
        ),
    )


class TestPose:
    def test_identity_pose_leaves_points_alone(self):
        point = Point3D(x=1.0, y=2.0, z=3.0)
        assert Pose().apply(point) == point

    def test_bounds_of_rotated_and_moved_piece(self):
        piece = Piece.of(PieceType.PT_2x4, 500.0, "p")
        # local (x, y, z) -> (-y, x, z), then +10 along X
        pose = Pose(
            rotation=((0, -1, 0), (1, 0, 0), (0, 0, 1)), translation=(10.0, 0.0, 0.0)
        )
        low, high = pose.bounds(piece)
        assert (low.x, low.y, low.z) == (-28.0, 0.0, 0.0)
        assert (high.x, high.y, high.z) == (10.0, 89.0, 500.0)


class TestRelativeRotation:
    @pytest.mark.parametrize("base_faces", ADJACENT)
    @pytest.mark.parametrize("target_faces", ADJACENT)
    def test_is_a_proper_signed_permutation(self, base_faces, target_faces):
        a = Piece.of(PieceType.PT_2x4, 500.0, "a")
        b = Piece.of(PieceType.PT_2x4, 300.0, "b")
        rotation = relative_rotation(_bound(a, *base_faces), _bound(b, *target_faces))
        assert rotation.dtype.kind == "i"
        assert set(np.abs(rotation).sum(axis=0)) == {1}
        assert set(np.abs(rotation).sum(axis=1)) == {1}
        assert round(np.linalg.det(rotation)) == 1

    @pytest.mark.parametrize("base_faces", ADJACENT)
    @pytest.mark.parametrize("target_faces", ADJACENT)
    def test_contact_faces_meet_and_edge_faces_are_flush(
        self, base_faces, target_faces
    ):
        a = Piece.of(PieceType.PT_2x4, 500.0, "a")
        b = Piece.of(PieceType.PT_2x4, 300.0, "b")
        rotation = relative_rotation(_bound(a, *base_faces), _bound(b, *target_faces))
        assert np.array_equal(rotation @ _vec(target_faces[0]), -_vec(base_faces[0]))
        assert np.array_equal(rotation @ _vec(target_faces[1]), _vec(base_faces[1]))


TABLE = (
    Path(__file__).parents[2] / "examples" / "nd_files" / "simple_table_compact.nd"
).read_text()
TABLE_LOOP_CLOSER = "leg_4 -[FL<100 TF<0]- apron_right"


def _box(placement, model, piece_id):
    low, high = placement.poses[piece_id].bounds(model.pieces[piece_id])
    return (low.x, low.y, low.z, high.x, high.y, high.z)


@st.composite
def anchors_on(draw, piece: Piece) -> Anchor:
    contact, edge = draw(st.sampled_from(ADJACENT))
    length = edge_length_of(Box(shape=get_shape(piece)), Edge(lhs=contact, rhs=edge))
    value = draw(st.floats(min_value=0, max_value=length, allow_nan=False))
    offset = draw(st.sampled_from([FromMin, FromMax]))(value=value)
    return Anchor(contact_face=contact, edge_shared_face=edge, offset=offset)


@st.composite
def tree_models(draw) -> Model:
    count = draw(st.integers(min_value=2, max_value=6))
    pieces = [
        Piece.of(
            draw(st.sampled_from([PieceType.PT_2x4, PieceType.PT_1x4])),
            draw(st.floats(min_value=50, max_value=1500, allow_nan=False)),
            f"p{i}",
        )
        for i in range(count)
    ]
    connections = []
    for i in range(1, count):
        base = pieces[draw(st.integers(min_value=0, max_value=i - 1))]
        connections.append(
            Connection(
                base=BoundAnchor(piece=base, anchor=draw(anchors_on(base))),
                target=BoundAnchor(piece=pieces[i], anchor=draw(anchors_on(pieces[i]))),
            )
        )
    return Model.of(pieces=pieces, connections=connections)


class TestSolvePlacement:
    def test_empty_model(self):
        placement = solve_placement(Model.of(pieces=[], connections=[]))
        assert placement.poses == {}
        assert placement.groups == ()

    def test_single_piece_sits_at_origin(self):
        placement = solve_placement(parse_dsl("(a:2x4 =500)"))
        assert placement.poses == {"a": Pose()}
        assert placement.groups == (("a",),)

    def test_target_is_placed_against_the_base_contact_face(self):
        model = parse_dsl("(a:2x4 =500)\n(b:2x4 =300)\na -[FL<100 DF<0]- b\n")
        placement = solve_placement(model)
        assert placement.poses["a"] == Pose()
        # b's down end touches a's front face (y=38) 100mm above a's down end
        assert _box(placement, model, "b") == (0.0, 38.0, 11.0, 38.0, 338.0, 100.0)

    def test_table_has_no_conflicts_and_one_group(self):
        placement = solve_placement(parse_dsl(TABLE))
        assert placement.conflicts == ()
        assert len(placement.groups) == 1

    def test_table_placement_does_not_depend_on_connection_order(self):
        model = parse_dsl(TABLE)
        connections = list(model.connections.values())
        expected = solve_placement(model).poses
        for reordered in (connections[::-1], connections[3:] + connections[:3]):
            shuffled = Model.of(
                pieces=list(model.pieces.values()), connections=reordered
            )
            assert solve_placement(shuffled).poses == expected

    def test_fractional_loop_closes_without_conflicts(self):
        source = (
            TABLE.replace("=622)", "=622.37)")
            .replace("=524)", "=523.91)")
            .replace("<100 ", "<100.123 ")
        )
        assert solve_placement(parse_dsl(source)).conflicts == ()

    def test_contradicting_position_is_reported_and_earlier_connection_wins(self):
        model = parse_dsl(
            "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\n"
            "a -[FL<100 DF<0]- b\na -[FL>100 DF<0]- c\nb -[RF<0 LF<0]- c\n"
        )
        placement = solve_placement(model)
        (conflict,) = placement.conflicts
        assert (conflict.base_id, conflict.target_id) == ("b", "c")
        assert (conflict.kind, conflict.axis) == ("contact", "z")
        assert conflict.mismatch_mm == pytest.approx(-389.0)
        assert conflict.loop == ("b", "a", "c")
        # c stays where a -[FL>100 DF<0]- c put it
        alone = parse_dsl("(a:2x4 =500)\n(c:2x4 =300)\na -[FL>100 DF<0]- c\n")
        assert _box(placement, model, "c") == _box(solve_placement(alone), alone, "c")

    def test_flush_conflict_is_named(self):
        placement = solve_placement(
            parse_dsl(
                "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\n"
                "a -[RF<0 LF<0]- b\na -[FL<100 DF<0]- c\nb -[FL<100 DF<0]- c\n"
            )
        )
        (conflict,) = placement.conflicts
        assert (conflict.kind, conflict.axis, conflict.mismatch_mm) == (
            "flush",
            "x",
            89.0,
        )

    def test_rotation_conflict_is_reported_once(self):
        placement = solve_placement(
            parse_dsl(
                "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\n"
                "a -[RF<0 LF<0]- b\na -[FL<100 DF<0]- c\nb -[RF<0 LF<0]- c\n"
            )
        )
        (conflict,) = placement.conflicts
        assert conflict.kind == "rotation"
        assert conflict.axis is None and conflict.mismatch_mm is None
        assert conflict.loop == ("b", "a", "c")

    def test_unconnected_groups_are_laid_out_side_by_side(self):
        placement = solve_placement(
            parse_dsl(
                "(a:2x4 =500)\n(b:2x4 =300)\n(floating:2x4 =300)\na -[FL<100 DF<0]- b\n"
            )
        )
        assert placement.groups == (("a", "b"), ("floating",))
        # the first group ends at x=89; the next starts 100mm further
        assert placement.poses["floating"] == Pose(translation=(189.0, 0.0, 0.0))


@given(tree_models())
@settings(max_examples=200, deadline=None)
def test_every_connection_holds_in_a_tree(model):
    placement = solve_placement(model)
    assert placement.conflicts == ()
    assert len(placement.groups) == 1
    for connection in model.connections.values():
        base_pose = placement.poses[connection.base.piece.id]
        target_pose = placement.poses[connection.target.piece.id]
        a = base_pose.apply(as_point_3d(connection.base))
        b = target_pose.apply(as_point_3d(connection.target))
        assert (a.x, a.y, a.z) == pytest.approx((b.x, b.y, b.z), abs=1e-5)
        base_rot, target_rot = (
            base_pose.rotation_matrix(),
            target_pose.rotation_matrix(),
        )
        assert np.array_equal(
            base_rot @ _vec(connection.base.anchor.contact_face),
            -(target_rot @ _vec(connection.target.anchor.contact_face)),
        )
        assert np.array_equal(
            base_rot @ _vec(connection.base.anchor.edge_shared_face),
            target_rot @ _vec(connection.target.anchor.edge_shared_face),
        )


@given(tree_models(), st.randoms(use_true_random=False))
@settings(max_examples=200, deadline=None)
def test_connection_order_does_not_matter(model, rng):
    connections = list(model.connections.values())
    rng.shuffle(connections)
    shuffled = Model.of(pieces=list(model.pieces.values()), connections=connections)
    expected = solve_placement(model).poses
    actual = solve_placement(shuffled).poses
    # Rotations are exact; random float offsets may round differently at 1e-6
    for piece_id, pose in expected.items():
        assert actual[piece_id].rotation == pose.rotation
        assert actual[piece_id].translation == pytest.approx(pose.translation, abs=1e-5)


@given(st.floats(min_value=0.5, max_value=500, allow_nan=False))
@settings(max_examples=50, deadline=None)
def test_shifting_a_loop_closing_connection_reports_exactly_that_shift(shift):
    source = TABLE.replace(
        TABLE_LOOP_CLOSER, f"leg_4 -[FL<{100 + shift} TF<0]- apron_right"
    )
    (conflict,) = solve_placement(parse_dsl(source)).conflicts
    assert (conflict.base_id, conflict.target_id) == ("leg_4", "apron_right")
    assert (conflict.kind, conflict.axis) == ("edge", "z")
    assert conflict.mismatch_mm == pytest.approx(shift, abs=1e-5)


class TestOverlaps:
    def test_touching_pieces_do_not_overlap(self):
        model = parse_dsl("(a:2x4 =500)\n(b:2x4 =300)\na -[FL<100 DF<0]- b\n")
        assert find_overlaps(model, solve_placement(model)) == ()

    def test_every_overlapping_pair_is_reported_with_its_volume(self):
        model = parse_dsl(
            "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\n(d:2x4 =300)\n(e:2x4 =300)\n"
            "a -[FL<100 DF<0]- b\na -[FL<100 DF<0]- c\n"
            "a -[RF<0 LF<0]- d\na -[RF<0 LF<0]- e\n"
        )
        overlaps = find_overlaps(model, solve_placement(model))
        assert [(o.lhs, o.rhs) for o in overlaps] == [("b", "c"), ("d", "e")]
        assert [o.volume for o in overlaps] == pytest.approx([89 * 38 * 300] * 2)

    def test_laid_out_groups_do_not_overlap(self):
        model = parse_dsl(
            "(a:2x4 =500)\n(b:2x4 =300)\n(floating:2x4 =300)\n(spare:1x4 =900)\n"
            "a -[FL<100 DF<0]- b\n"
        )
        assert find_overlaps(model, solve_placement(model)) == ()


class TestOverallBounds:
    def test_bounds_cover_every_piece(self):
        model = parse_dsl("(a:2x4 =500)\n(b:2x4 =300)\na -[FL<100 DF<0]- b\n")
        low, high = overall_bounds(model, solve_placement(model))
        assert (low.x, low.y, low.z) == (0.0, 0.0, 0.0)
        assert (high.x, high.y, high.z) == (89.0, 338.0, 500.0)

    def test_empty_model_has_empty_bounds(self):
        model = Model.of(pieces=[], connections=[])
        low, high = overall_bounds(model, solve_placement(model))
        assert low == high == Point3D(x=0.0, y=0.0, z=0.0)


class TestOverlapRounding:
    def test_touching_pieces_with_long_decimal_lengths_do_not_overlap(self):
        # positions are rounded to 1e-6mm but extents use the exact length
        model = parse_dsl("(a:2x4 =333.3333333)\n(b:2x4 =300)\na -[TF<0 DF<0]- b\n")
        assert find_overlaps(model, solve_placement(model)) == ()
