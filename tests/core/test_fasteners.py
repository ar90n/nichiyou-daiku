"""Tests for laying out dowels and screws in the contact area."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.assembly.fasteners import (
    _Bore,
    _bores_meet,
    _surface_point,
    find_hole_collisions,
    layout_fasteners,
    pilot_diameter,
)
from nichiyou_daiku.core.assembly.models import Fastener, Hole
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
TYPES = list(PieceType)


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

    def test_square_contact_with_room_for_two_uses_the_lower_axis(self):
        # 38 x 38 contact on a's left face (axes y and z): y is the long side
        connection, fasteners, issue = _layout(
            "(a:2x4 =500)\n(b:2x4 =300)\na -[LF<100 TL<0 D(4, 30)]- b\n"
        )
        assert issue is None
        assert [_base_point(connection, f) for f in fasteners] == [
            (0.0, 9.5, 81.0),
            (0.0, 28.5, 81.0),
        ]

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
        # Pilot holes are about 65% of the screw; the screw keeps its own size
        assert {f.target_hole for f in fasteners} == {Hole(diameter=2.0)}
        assert {f.base_hole for f in fasteners} == {Hole(diameter=2.0, depth=6.0)}
        assert {f.diameter for f in fasteners} == {3.3}
        assert {f.kind for f in fasteners} == {"screw"}


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
            length=target_thickness + draw(st.floats(1.0, min(base_depth - 1.0, 30.0))),
        )
    return Connection(
        base=BoundAnchor(piece=base, anchor=anchor(base, base_faces)),
        target=BoundAnchor(piece=target, anchor=anchor(target, target_faces)),
        type=connection_type,
    )


def _follows_layout_rule(points, low, sizes, long_axis, short_axis, diameter, slack):
    """Centred across the short side; at 1/4 and 3/4 of the long side, or in
    the middle when L/2 < 2d (either is fine within slack of the boundary)."""
    long_size, short_size = sizes[long_axis], sizes[short_axis]
    if any(
        abs(p[short_axis] - low[short_axis] - short_size / 2) > slack for p in points
    ):
        return False
    along = sorted(p[long_axis] - low[long_axis] for p in points)
    expected = []
    if long_size / 2 >= 2 * diameter - slack:
        expected.append([long_size / 4, 3 * long_size / 4])
    if long_size / 2 < 2 * diameter + slack:
        expected.append([long_size / 2])
    return any(
        len(e) == len(along) and all(abs(a - b) <= slack for a, b in zip(along, e))
        for e in expected
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

    # World poses are rounded to 1e-6mm while the layout uses the exact
    # relative pose, so allow that much slack at the S = 2d boundary.
    slack = 1e-5
    if issue is not None:
        assert fasteners == ()
        assert shortest <= slack or shortest < 2 * diameter + slack
        return

    assert shortest >= 2 * diameter - slack
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
        assert on_base == pytest.approx(on_target, abs=slack)
        points.append(on_base)

    # The base is the first piece, so world axes are the base's axes; on a
    # tie the lower-numbered axis is the long one.
    first, second = in_plane
    assignments = [(first, second), (second, first)]
    if abs(sizes[first] - sizes[second]) > slack:
        assignments = [
            assignments[0] if sizes[first] > sizes[second] else assignments[1]
        ]
    assert any(
        _follows_layout_rule(points, low, sizes, long_axis, short_axis, diameter, slack)
        for long_axis, short_axis in assignments
    )


POST_AND_FRONT_RAIL = (
    "(post:2x4 =600)\n(front:2x4 =300)\n(other:2x4 =300)\n"
    "post -[FL<300 DF<0 D(4, {front})]- front\n"
)


def _fastener_issues(source: str) -> list[tuple[str, str, str]]:
    assembly = Assembly.of(parse_dsl(source))
    return [(i.base_id, i.target_id, i.message) for i in assembly.fastener_issues]


class TestHoleCollisions:
    def test_holes_meeting_from_opposite_faces_are_reported_on_the_later_connection(
        self,
    ):
        # 20mm from the front and 20mm from the back of a 38mm post overlap
        source = POST_AND_FRONT_RAIL.format(front=40) + (
            "post -[BL<300 DB<0 D(4, 40)]- other\n"
        )
        assert _fastener_issues(source) == [
            (
                "post",
                "other",
                "dowel hole in 'post' runs into a dowel hole of connection "
                "post -> front",
            )
        ]

    def test_holes_that_stop_short_of_each_other_are_fine(self):
        source = POST_AND_FRONT_RAIL.format(front=30) + (
            "post -[BL<300 DB<0 D(4, 30)]- other\n"
        )
        assert _fastener_issues(source) == []

    def test_holes_crossing_from_adjacent_faces_are_reported(self):
        source = POST_AND_FRONT_RAIL.format(front=60) + (
            "post -[LF<211 DF<0 D(4, 60)]- other\n"
        )
        assert [issue[:2] for issue in _fastener_issues(source)] == [("post", "other")]

    def test_holes_that_only_touch_are_fine(self):
        # The side hole stops at x=15; the front hole's wall is at x=19-4=15
        source = POST_AND_FRONT_RAIL.format(front=60) + (
            "post -[LF<211 DF<0 D(4, 30)]- other\n"
        )
        assert _fastener_issues(source) == []

    def test_colliding_fasteners_are_still_drilled(self):
        source = POST_AND_FRONT_RAIL.format(front=40) + (
            "post -[BL<300 DB<0 D(4, 40)]- other\n"
        )
        assert len(Assembly.of(parse_dsl(source)).fasteners) == 4

    def test_a_collision_names_the_piece_the_other_connection_and_both_holes(self):
        source = POST_AND_FRONT_RAIL.format(front=40) + (
            "post -[BL<300 DB<0 D(4, 40)]- other\n"
        )
        [issue] = Assembly.of(parse_dsl(source)).fastener_issues
        assert issue.piece_id == "post"
        assert issue.other == ("post", "front")
        assert issue.holes is not None
        (later, later_hole), (earlier, earlier_hole) = issue.holes
        # This connection drills the post's back, the earlier one its front
        assert (later.face, earlier.face) == ("back", "front")
        assert later_hole == earlier_hole == Hole(diameter=8.0, depth=20.0)

    def test_a_fastener_without_room_has_no_holes(self):
        source = "(a:2x4 =500)\n(b:1x4 =300)\na -[FL<100 DF<0 D(5, 30)]- b\n"
        [issue] = Assembly.of(parse_dsl(source)).fastener_issues
        assert (issue.piece_id, issue.other, issue.holes) == (None, None, None)


def _bore_along_z(x: float, y: float, low: float, high: float) -> _Bore:
    return _Bore(axis=2, low=low, high=high, center=np.array([x, y, low]), radius=4.0)


def _bore_along_x(y: float, z: float, low: float = -50.0) -> _Bore:
    return _Bore(axis=0, low=low, high=50, center=np.array([low, y, z]), radius=4.0)


@pytest.mark.parametrize(
    ("bore", "meets"),
    [
        # Passes 3mm beyond the end of the z bore: the walls still overlap
        (_bore_along_x(y=0, z=13), True),
        (_bore_along_x(y=0, z=14.5), False),
        # 3mm beyond the end of both bores: reach is 2 * sqrt(4^2 - 3^2) = 5.29
        (_bore_along_x(y=5.0, z=13, low=3), True),
        (_bore_along_x(y=5.5, z=13, low=3), False),
    ],
)
def test_perpendicular_bores_meet_only_where_their_walls_overlap(bore, meets):
    z_bore = _bore_along_z(x=0, y=0, low=0, high=10)
    assert _bores_meet(z_bore, bore) is meets
    assert _bores_meet(bore, z_bore) is meets


@pytest.mark.parametrize(("screw", "pilot"), [(3.3, 2.0), (3.8, 2.5), (4.2, 2.5)])
def test_screw_pilot_holes_are_about_two_thirds_of_the_screw(screw, pilot):
    # A hole as wide as the screw would leave its thread nothing to bite
    assert pilot_diameter(screw) == pilot


def test_a_tiny_screw_still_gets_a_pilot_hole():
    # 65% of 0.3 rounds to 0: a hole of no width would draw and drill nothing
    assert pilot_diameter(0.3) == 0.5


def test_screw_bodies_collide_even_where_their_pilot_holes_do_not():
    # Two 3.8mm screws 3mm apart, from the front and the back of a 38mm post:
    # their 2.5mm pilot holes miss each other, the screws themselves do not
    post = Piece.of(PieceType.PT_2x4, 600.0, "post")
    targets = {
        name: Piece.of(PieceType.PT_1x4, 300.0, name) for name in ("front", "back")
    }
    box = Box(shape=get_shape(post))

    def screw(target: str, x: float) -> Fastener:
        face = "front" if target == "front" else "back"
        at = _surface_point(
            box, face, np.array([x, 38.0 if face == "front" else 0.0, 300.0])
        )
        return Fastener(
            base_id="post",
            target_id=target,
            kind="screw",
            diameter=3.8,
            base_position=at,
            target_position=at,
            base_hole=Hole(diameter=2.5, depth=20.0),
            target_hole=Hole(diameter=2.5),
        )

    [issue] = find_hole_collisions(
        [screw("front", 44.5), screw("back", 47.5)], {"post": post, **targets}
    )
    assert (issue.base_id, issue.target_id, issue.piece_id) == ("post", "back", "post")
    # The issue reports the space the screws take, not the pilot holes
    assert issue.holes is not None
    assert [hole.diameter for _, hole in issue.holes] == [3.8, 3.8]
