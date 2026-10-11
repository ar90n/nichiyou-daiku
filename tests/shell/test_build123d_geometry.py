"""Geometry tests for build123d export that run against real build123d."""

import math
from pathlib import Path

import pytest

pytest.importorskip("build123d")

from nichiyou_daiku.core.assembly import Assembly  # noqa: E402
from nichiyou_daiku.core.geometry import Box, Shape3D  # noqa: E402
from nichiyou_daiku.dsl import parse_dsl  # noqa: E402
from nichiyou_daiku.shell.build123d_export import (  # noqa: E402
    _create_piece_from,
    assembly_to_build123d,
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


class TestRendersCorePlacement:
    @pytest.mark.parametrize(
        "path",
        sorted((Path(__file__).parents[2] / "examples" / "nd_files").glob("*.nd")),
        ids=lambda p: p.name,
    )
    def test_each_part_sits_where_the_placement_puts_it(self, path):
        assembly = Assembly.of(parse_dsl(path.read_text()))
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
            ) == pytest.approx((low.x, low.y, low.z, high.x, high.y, high.z), abs=1e-6)

    def test_unconnected_group_is_rendered_beside_the_rest(self):
        assembly = Assembly.of(
            parse_dsl(
                "(a:2x4 =500)\n(b:2x4 =300)\n(floating:2x4 =300)\na -[FL<100 DF<0]- b\n"
            )
        )
        compound = assembly_to_build123d(assembly, fillet_radius=0)
        floating = {c.label: c for c in compound.children}["floating"]
        assert floating.bounding_box().min.X == pytest.approx(189.0)
