"""Tests for dowel preset DSL parsing."""

import pytest

from nichiyou_daiku.core.connection import DowelConnection
from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.dsl.exceptions import DSLValidationError


class TestDowelPresetParsing:
    """Test dowel preset parsing in DSL."""

    def test_should_parse_valid_dowel_preset(self):
        """Should parse valid dowel preset D(:8x30)."""
        dsl = """
        (piece1:2x4 =1000)
        (piece2:2x4 =800)

        piece1 -[TF<0 BD<0 D(:8x30)]- piece2
        """
        model = parse_dsl(dsl)

        conn = model.connections[("piece1", "piece2")]
        assert isinstance(conn.type, DowelConnection)
        # Diameter 8mm -> radius 4mm
        assert conn.type.radius == 4.0
        assert conn.type.depth == 30.0

    @pytest.mark.parametrize(
        "preset,expected_radius,expected_depth",
        [
            ("6x25", 3.0, 25.0),
            ("6x30", 3.0, 30.0),
            ("8x25", 4.0, 25.0),
            ("8x30", 4.0, 30.0),
            ("8x40", 4.0, 40.0),
            ("10x30", 5.0, 30.0),
            ("10x40", 5.0, 40.0),
            ("12x40", 6.0, 40.0),
        ],
    )
    def test_should_parse_standard_preset(
        self, preset: str, expected_radius: float, expected_depth: float
    ):
        """Should parse standard dowel preset."""
        dsl = f"""
        (p1:2x4 =1000)
        (p2:2x4 =800)

        p1 -[TF<0 BD<0 D(:{preset})]- p2
        """
        model = parse_dsl(dsl)
        conn = model.connections[("p1", "p2")]
        assert conn.type.radius == expected_radius
        assert conn.type.depth == expected_depth

    def test_should_reject_invalid_preset(self):
        """Should reject invalid dowel preset."""
        dsl = """
        (piece1:2x4 =1000)
        (piece2:2x4 =800)

        piece1 -[TF<0 BD<0 D(:9x99)]- piece2
        """
        with pytest.raises(DSLValidationError, match="Unknown dowel preset"):
            parse_dsl(dsl)

    def test_should_still_support_numeric_format(self):
        """Should still support numeric format D(radius, depth)."""
        dsl = """
        (piece1:2x4 =1000)
        (piece2:2x4 =800)

        piece1 -[TF<0 BD<0 D(4.0, 30.0)]- piece2
        """
        model = parse_dsl(dsl)

        conn = model.connections[("piece1", "piece2")]
        assert isinstance(conn.type, DowelConnection)
        assert conn.type.radius == 4.0
        assert conn.type.depth == 30.0

    def test_should_allow_mixed_formats_in_same_file(self):
        """Should allow both preset and numeric formats in the same file."""
        dsl = """
        (p1:2x4 =1000)
        (p2:2x4 =800)
        (p3:2x4 =600)

        p1 -[TF<0 BD<0 D(:8x30)]- p2
        p2 -[TF<0 BD<0 D(4.0, 25.0)]- p3
        """
        model = parse_dsl(dsl)

        # First connection uses preset
        conn1 = model.connections[("p1", "p2")]
        assert conn1.type.radius == 4.0
        assert conn1.type.depth == 30.0

        # Second connection uses numeric
        conn2 = model.connections[("p2", "p3")]
        assert conn2.type.radius == 4.0
        assert conn2.type.depth == 25.0
