"""Tests for assembly module."""

from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.assembly import Assembly, Hole
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.geometry import Box, FromMin
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
from nichiyou_daiku.core.placement import solve_placement
from nichiyou_daiku.dsl import parse_dsl

T_JOINT = "(leg:2x4 =700)\n(apron:2x4 =500)\nleg -[FL<100 DF<0 {kind}]- apron\n"


def _assembly(source: str) -> Assembly:
    return Assembly.of(parse_dsl(source))


class TestBox:
    def test_should_handle_different_piece_lengths(self):
        for length in [500.0, 1000.0, 2000.0]:
            box = Box(shape=get_shape(Piece.of(PieceType.PT_2x4, length)))
            assert (box.shape.width, box.shape.height, box.shape.length) == (
                89.0,
                38.0,
                length,
            )


class TestFastenersAndHoles:
    def test_vanilla_connection_has_no_fasteners_or_holes(self):
        assembly = _assembly(T_JOINT.format(kind="V"))
        assert assembly.fasteners == ()
        assert assembly.fastener_issues == ()
        assert assembly.pilot_holes == {}

    def test_dowels_drill_matching_holes_in_both_pieces(self):
        assembly = _assembly(T_JOINT.format(kind="D(4, 30)"))
        assert len(assembly.fasteners) == 2
        for piece_id, face in (("leg", "front"), ("apron", "down")):
            holes = assembly.pilot_holes[piece_id]
            assert [hole for _, hole in holes] == [Hole(diameter=8.0, depth=15.0)] * 2
            assert {position.face for position, _ in holes} == {face}

    def test_screws_pass_through_the_target_into_the_base(self):
        assembly = _assembly(
            "(base:2x4 =500)\n(target:1x4 =300)\nbase -[FL<100 BL<0 S(Slim:3.3x25)]- target\n"
        )
        assert [hole for _, hole in assembly.pilot_holes["target"]] == [
            Hole(diameter=3.3)
        ] * 2
        assert [hole for _, hole in assembly.pilot_holes["base"]] == [
            Hole(diameter=3.3, depth=6.0)
        ] * 2

    def test_fastener_that_does_not_fit_is_reported_not_drilled(self):
        assembly = _assembly(
            "(a:2x4 =500)\n(b:1x4 =300)\na -[FL<100 DF<0 D(5, 30)]- b\n"
        )
        assert assembly.fasteners == ()
        assert assembly.pilot_holes == {}
        (issue,) = assembly.fastener_issues
        assert (issue.base_id, issue.target_id, issue.kind) == ("a", "b", "dowel")
        assert "too narrow" in issue.message

    def test_former_not_implemented_face_combination_now_lays_out(self):
        # front/back to front/back with left edges used to raise NotImplementedError
        assembly = _assembly(
            "(a:2x4 =500)\n(b:2x4 =500)\na -[FL<100 BL<100 D(4, 30)]- b\n"
        )
        assert len(assembly.fasteners) == 2
        assert assembly.fastener_issues == ()


class TestAssemblyPlacement:
    def test_assembly_carries_the_solved_placement(self):
        a = Piece.of(PieceType.PT_2x4, 500.0, "a")
        b = Piece.of(PieceType.PT_2x4, 300.0, "b")
        model = Model.of(
            pieces=[a, b],
            connections=[
                Connection(
                    base=BoundAnchor(
                        piece=a,
                        anchor=Anchor(
                            contact_face="front",
                            edge_shared_face="left",
                            offset=FromMin(value=100),
                        ),
                    ),
                    target=BoundAnchor(
                        piece=b,
                        anchor=Anchor(
                            contact_face="down",
                            edge_shared_face="front",
                            offset=FromMin(value=0),
                        ),
                    ),
                )
            ],
        )
        assert Assembly.of(model).placement == solve_placement(model)


class TestFastenersOfRejectedConnections:
    def test_connection_rejected_by_placement_gets_no_fasteners(self):
        # b -> c contradicts the placement fixed by a -> b and a -> c
        assembly = _assembly(
            "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\n"
            "a -[FL<100 DF<0]- b\na -[FL>100 DF<0]- c\nb -[RF<0 LF<0 D(4, 30)]- c\n"
        )
        assert [(c.base_id, c.target_id) for c in assembly.placement.conflicts] == [
            ("b", "c")
        ]
        assert assembly.fasteners == ()
        assert assembly.pilot_holes == {}
