"""Tests for laying out dowels and screws in the contact area."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.assembly.fasteners import layout_fasteners
from nichiyou_daiku.core.assembly.models import Hole
from nichiyou_daiku.core.connection import (
    Connection,
    DowelConnection,
    ScrewConnection,
    _get_dimension_for_face,
)
from nichiyou_daiku.core.geometry import (
    Box,
    Edge,
    FromMax,
    FromMin,
    Point3D,
    edge_length_of,
    is_adjacent,
)
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
from nichiyou_daiku.core.placement import solve_placement
from nichiyou_daiku.dsl import parse_dsl

FACES = ["top", "down", "left", "right", "front", "back"]
ADJACENT = [(c, e) for c in FACES for e in FACES if is_adjacent(c, e)]
TYPES = [PieceType.PT_2x4, PieceType.PT_1x4]


def _layout(source: str):
    connection = next(iter(parse_dsl(source).connections.values()))
    fasteners, issue = layout_fasteners(connection)
    return connection, fasteners, issue


def _xyz(point: Point3D) -> np.ndarray:
    return np.array([point.x, point.y, point.z])


def _base_point(connection: Connection, fastener) -> tuple[float, float, float]:
    point = Point3D.of(
        Box(shape=get_shape(connection.base.piece)), fastener.base_position
    )
    return (round(point.x, 6), round(point.y, 6), round(point.z, 6))


class TestLayoutFasteners:
    def test_vanilla_connection_has_no_fasteners(self):
        _, fasteners, issue = _layout(
            "(a:2x4 =500)\n(b:2x4 =300)\na -[FL<100 DF<0]- b\n"
        )
        assert fasteners == ()
        assert issue is None

    def test_dowels_in_a_t_joint(self):
        connection, fasteners, issue = _layout(
            "(leg:2x4 =700)\n(apron:2x4 =500)\nleg -[FL<100 DF<0 D(4, 30)]- apron\n"
        )
        assert issue is None
        assert [_base_point(connection, f) for f in fasteners] == [
            (19.0, 38.0, 33.25),
            (19.0, 38.0, 77.75),
        ]
        assert {f.base_position.face for f in fasteners} == {"front"}
        assert {f.target_position.face for f in fasteners} == {"down"}
        assert {f.base_hole for f in fasteners} == {Hole(diameter=8.0, depth=15.0)}
        assert {f.target_hole for f in fasteners} == {Hole(diameter=8.0, depth=15.0)}
        assert {(f.base_id, f.target_id, f.kind) for f in fasteners} == {
            ("leg", "apron", "dowel")
        }

    def test_dowel_fits_a_1x4_edge(self):
        connection, fasteners, issue = _layout(
            "(a:2x4 =500)\n(b:1x4 =300)\na -[FL<100 DF<0 D(4, 30)]- b\n"
        )
        assert issue is None
        assert [_base_point(connection, f) for f in fasteners] == [
            (9.5, 38.0, 33.25),
            (9.5, 38.0, 77.75),
        ]

    def test_too_narrow_contact_is_reported(self):
        _, fasteners, issue = _layout(
            "(a:2x4 =500)\n(b:1x4 =300)\na -[FL<100 DF<0 D(5, 30)]- b\n"
        )
        assert fasteners == ()
        assert issue is not None
        assert (issue.base_id, issue.target_id, issue.kind) == ("a", "b", "dowel")
        assert issue.message == (
            "contact area 19.0 x 89.0mm is too narrow for a 10.0mm dowel (needs 20.0mm)"
        )

    def test_square_contact_gets_a_single_centred_dowel(self):
        connection, fasteners, issue = _layout(
            "(a:2x4 =500)\n(b:2x4 =300)\na -[LF<100 TL<0 D(5, 30)]- b\n"
        )
        assert issue is None
        assert [_base_point(connection, f) for f in fasteners] == [(0.0, 19.0, 81.0)]

    def test_edge_only_contact_is_reported(self):
        _, fasteners, issue = _layout(
            "(a:2x4 =500)\n(b:2x4 =300)\na -[FT<0 DF<0 D(4, 30)]- b\n"
        )
        assert fasteners == ()
        assert issue is not None
        assert issue.message == "pieces do not share a contact area"

    def test_screws_pass_through_the_target_into_the_base(self):
        _, fasteners, issue = _layout(
            "(base:2x4 =500)\n(target:1x4 =300)\nbase -[FL<100 BL<0 S(Slim:3.3x25)]- target\n"
        )
        assert issue is None
        assert len(fasteners) == 2
        assert {f.target_hole for f in fasteners} == {Hole(diameter=3.3)}
        assert {f.base_hole for f in fasteners} == {Hole(diameter=3.3, depth=6.0)}
        assert {f.kind for f in fasteners} == {"screw"}

    @pytest.mark.parametrize("base_faces", ADJACENT)
    @pytest.mark.parametrize("target_faces", ADJACENT)
    def test_every_face_combination_lays_out_without_errors(
        self, base_faces, target_faces
    ):
        base = Piece.of(PieceType.PT_2x4, 500.0, "base")
        target = Piece.of(PieceType.PT_2x4, 300.0, "target")
        base_length = edge_length_of(
            Box(shape=get_shape(base)), Edge(lhs=base_faces[0], rhs=base_faces[1])
        )
        target_length = edge_length_of(
            Box(shape=get_shape(target)), Edge(lhs=target_faces[0], rhs=target_faces[1])
        )
        connection = Connection(
            base=BoundAnchor(
                piece=base,
                anchor=Anchor(
                    contact_face=base_faces[0],
                    edge_shared_face=base_faces[1],
                    offset=FromMin(value=base_length * 0.3),
                ),
            ),
            target=BoundAnchor(
                piece=target,
                anchor=Anchor(
                    contact_face=target_faces[0],
                    edge_shared_face=target_faces[1],
                    offset=FromMax(value=target_length * 0.2),
                ),
            ),
            type=DowelConnection(radius=3.0, depth=12.0),
        )
        fasteners, issue = layout_fasteners(connection)
        assert (len(fasteners) in (1, 2)) != (issue is not None)


@st.composite
def fastened_connections(draw) -> Connection:
    base = Piece.of(draw(st.sampled_from(TYPES)), draw(st.floats(100, 1000)), "base")
    target = Piece.of(
        draw(st.sampled_from(TYPES)), draw(st.floats(100, 1000)), "target"
    )
    kind = draw(st.sampled_from(["dowel", "screw"]))
    base_faces = draw(st.sampled_from(ADJACENT))
    target_faces = draw(
        st.sampled_from(
            [f for f in ADJACENT if kind == "dowel" or f[0] in ("front", "back")]
        )
    )

    def anchor(piece: Piece, faces) -> Anchor:
        length = edge_length_of(
            Box(shape=get_shape(piece)), Edge(lhs=faces[0], rhs=faces[1])
        )
        value = draw(st.floats(min_value=0, max_value=length, allow_nan=False))
        offset = draw(st.sampled_from([FromMin, FromMax]))(value=value)
        return Anchor(contact_face=faces[0], edge_shared_face=faces[1], offset=offset)

    if kind == "dowel":
        connection_type = DowelConnection(radius=draw(st.floats(2.0, 5.0)), depth=10.0)
    else:
        target_thickness = _get_dimension_for_face(get_shape(target), target_faces[0])
        base_depth = _get_dimension_for_face(get_shape(base), base_faces[0])
        connection_type = ScrewConnection(
            diameter=draw(st.floats(2.0, 5.0)),
            length=target_thickness + draw(st.floats(1.0, min(base_depth, 30.0))),
        )
    return Connection(
        base=BoundAnchor(piece=base, anchor=anchor(base, base_faces)),
        target=BoundAnchor(piece=target, anchor=anchor(target, target_faces)),
        type=connection_type,
    )


@given(fastened_connections())
@settings(max_examples=300, deadline=None)
def test_fasteners_sit_inside_the_shared_contact_area(connection):
    fasteners, issue = layout_fasteners(connection)
    base, target = connection.base.piece, connection.target.piece
    placement = solve_placement(
        Model.of(pieces=[base, target], connections=[connection])
    )
    base_low, base_high = placement.poses["base"].bounds(base)
    target_low, target_high = placement.poses["target"].bounds(target)
    low = np.maximum(_xyz(base_low), _xyz(target_low))
    high = np.minimum(_xyz(base_high), _xyz(target_high))
    sizes = high - low
    plane_axis = int(np.argmin(np.abs(sizes)))
    in_plane = [axis for axis in range(3) if axis != plane_axis]
    shortest = min(sizes[axis] for axis in in_plane)
    match connection.type:
        case DowelConnection(radius=radius):
            diameter = radius * 2
        case ScrewConnection(diameter=screw_diameter):
            diameter = screw_diameter

    if issue is not None:
        assert fasteners == ()
        assert shortest <= 1e-6 or shortest < 2 * diameter
        return

    assert shortest >= 2 * diameter - 1e-9
    assert len(fasteners) in (1, 2)
    points = []
    for fastener in fasteners:
        on_base = _xyz(
            placement.poses["base"].apply(
                Point3D.of(Box(shape=get_shape(base)), fastener.base_position)
            )
        )
        on_target = _xyz(
            placement.poses["target"].apply(
                Point3D.of(Box(shape=get_shape(target)), fastener.target_position)
            )
        )
        assert on_base == pytest.approx(on_target, abs=1e-6)
        for axis in in_plane:
            assert (
                low[axis] + diameter - 1e-6
                <= on_base[axis]
                <= high[axis] - diameter + 1e-6
            )
        points.append(on_base)
    if len(points) == 2:
        assert np.linalg.norm(points[0] - points[1]) >= 2 * diameter - 1e-6
