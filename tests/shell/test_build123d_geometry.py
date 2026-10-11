"""Geometry tests for build123d export that run against real build123d."""

import math

import pytest

pytest.importorskip("build123d")

from nichiyou_daiku.core.assembly import Assembly  # noqa: E402
from nichiyou_daiku.core.geometry import Box, Shape3D  # noqa: E402
from nichiyou_daiku.dsl import parse_dsl  # noqa: E402
from nichiyou_daiku.shell.build123d_export import (  # noqa: E402
    _create_piece_from,
    assembly_to_build123d,
    check_overlap,
)


def _box(width: float, height: float, length: float) -> Box:
    return Box(shape=Shape3D(width=width, height=height, length=length))


def _corner_loss(radius: float) -> float:
    """Cross-section area removed by rounding one edge."""
    return (1 - math.pi / 4) * radius**2


class TestAssemblyToBuild123d:
    def test_empty_assembly_gives_empty_compound(self):
        from nichiyou_daiku.core.model import Model

        empty = Assembly.of(Model.of(pieces=[], connections=[]))
        assert list(assembly_to_build123d(empty, fillet_radius=0).children) == []

    def test_one_labelled_part_per_piece(self):
        compound = _compound(
            """
            (a:2x4 =500)
            (b:1x4 =300)
            a -[FL<100 DF<0]- b
            """
        )
        sizes = {
            ch.label: sorted(round(v, 3) for v in tuple(ch.bounding_box().size))
            for ch in compound.children
        }
        assert sizes == {"a": [38.0, 89.0, 500.0], "b": [19.0, 89.0, 300.0]}

    def test_target_is_placed_against_the_base_contact_face(self):
        compound = _compound(
            """
            (a:2x4 =500)
            (b:2x4 =300)
            a -[FL<100 DF<0]- b
            """
        )
        b = {ch.label: ch.bounding_box() for ch in compound.children}["b"]
        # b's down end touches a's front face (y=38) and b runs away from it
        assert (b.min.Y, b.max.Y) == pytest.approx((38.0, 338.0))

    def test_dowel_holes_are_drilled(self):
        dsl = """
            (a:2x4 =500)
            (b:2x4 =500)
            a -[FT>35 BD<20 {dowel}]- b
        """
        plain = _compound(dsl.format(dowel="V"))
        drilled = _compound(dsl.format(dowel="D(4, 30)"))
        removed = sum(ch.volume for ch in plain.children) - sum(
            ch.volume for ch in drilled.children
        )
        # four holes, 8mm across and 15mm deep
        assert removed == pytest.approx(4 * math.pi * 4.0**2 * 15.0, rel=1e-3)


class TestFillet:
    def test_rounds_the_four_long_edges(self):
        length = 500.0
        part = _create_piece_from("p", _box(89.0, 38.0, length), fillet_radius=5.0)
        expected = 89.0 * 38.0 * length - 4 * _corner_loss(5.0) * length
        assert part.volume == pytest.approx(expected, rel=1e-4)

    def test_short_piece_can_be_filleted(self):
        part = _create_piece_from("p", _box(89.0, 38.0, 8.0), fillet_radius=5.0)
        assert part.volume > 0

    def test_radius_larger_than_half_the_thickness_is_clamped(self):
        # 1x4 is 19mm thick; a 10mm radius cannot fit
        part = _create_piece_from("p", _box(89.0, 19.0, 300.0), fillet_radius=10.0)
        assert 0 < part.volume < 89.0 * 19.0 * 300.0


def _compound(dsl: str):
    return assembly_to_build123d(Assembly.of(parse_dsl(dsl)), fillet_radius=0)


class TestCheckOverlap:
    def test_reports_every_overlapping_pair(self):
        # b and c both sit at the same place on a's front face
        compound = _compound(
            """
            (a:2x4 =500)
            (b:2x4 =300)
            (c:2x4 =300)
            (d:2x4 =300)
            (e:2x4 =300)
            a -[FL<100 DF<0]- b
            a -[FL<100 DF<0]- c
            a -[RF<0 LF<0]- d
            a -[RF<0 LF<0]- e
            """
        )
        result = check_overlap(compound)
        assert result.has_overlap
        assert sorted(tuple(sorted(p)) for p in result.overlapping_pairs) == [
            ("b", "c"),
            ("d", "e"),
        ]
        assert result.volume == pytest.approx(2 * 89.0 * 38.0 * 300.0, rel=1e-3)

    def test_touching_pieces_do_not_overlap(self):
        compound = _compound(
            """
            (a:2x4 =500)
            (b:2x4 =300)
            a -[FL<100 DF<0]- b
            """
        )
        assert not check_overlap(compound).has_overlap

    def test_unconnected_piece_left_at_origin_is_reported(self):
        compound = _compound(
            """
            (a:2x4 =500)
            (b:2x4 =300)
            (floating:2x4 =300)
            a -[FL<100 DF<0]- b
            """
        )
        pairs = [tuple(sorted(p)) for p in check_overlap(compound).overlapping_pairs]
        assert ("a", "floating") in pairs


class TestJointMismatches:
    def test_simple_connection_has_no_mismatch(self):
        from nichiyou_daiku.shell.build123d_export import find_joint_mismatches

        assembly = Assembly.of(
            parse_dsl(
                """
                (a:2x4 =300)
                (b:2x4 =300)
                a -[FL<100 DF<0]- b
                """
            )
        )
        compound = assembly_to_build123d(assembly, fillet_radius=0)
        assert find_joint_mismatches(assembly, compound) == []

    def test_contradicting_connection_is_reported(self):
        from nichiyou_daiku.shell.build123d_export import find_joint_mismatches

        # a-b fixes b; a-c fixes c; b-c then asks for a position c cannot take
        assembly = Assembly.of(
            parse_dsl(
                """
                (a:2x4 =500)
                (b:2x4 =300)
                (c:2x4 =300)
                a -[FL<100 DF<0]- b
                a -[FL>100 DF<0]- c
                b -[RF<0 LF<0]- c
                """
            )
        )
        compound = assembly_to_build123d(assembly, fillet_radius=0)
        mismatches = find_joint_mismatches(assembly, compound)
        assert len(mismatches) >= 1
        assert all(distance > 1.0 for _, _, distance in mismatches)

    def test_later_connection_does_not_move_an_already_placed_piece(self):
        base = """
            (a:2x4 =500)
            (b:2x4 =300)
            (c:2x4 =300)
            a -[FL<100 DF<0]- b
            a -[FL>100 DF<0]- c
        """
        contradiction = "b -[RF<0 LF<0]- c\n"
        placed = {ch.label: ch.bounding_box() for ch in _compound(base).children}
        with_contradiction = {
            ch.label: ch.bounding_box()
            for ch in _compound(base + contradiction).children
        }
        for label in ("a", "b", "c"):
            assert tuple(with_contradiction[label].min) == pytest.approx(
                tuple(placed[label].min)
            )


class TestChecksDoNotDisturbEachOther:
    def test_overlap_check_leaves_joint_locations_alone(self):
        from nichiyou_daiku.shell.build123d_export import find_joint_mismatches

        # b and c overlap, so the overlap check intersects them; every joint
        # is still where its connection put it
        assembly = Assembly.of(
            parse_dsl(
                """
                (a:2x4 =500)
                (b:2x4 =300)
                (c:2x4 =300)
                a -[FL<100 DF<0]- b
                a -[FL<100 DF<0]- c
                """
            )
        )
        compound = assembly_to_build123d(assembly, fillet_radius=0)
        assert check_overlap(compound).has_overlap
        assert find_joint_mismatches(assembly, compound) == []
