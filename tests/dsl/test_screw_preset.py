"""Tests for DSL screw preset support."""

import pytest

from nichiyou_daiku.core.connection import ScrewConnection
from nichiyou_daiku.core.screw import find_preset, SlimScrew, CoarseThreadScrew
from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.dsl.exceptions import DSLValidationError


class TestFindPreset:
    """Tests for find_preset helper function."""

    def test_find_slim_screw_preset(self):
        """Should find valid slim screw preset."""
        result = find_preset("Slim", 3.3, 50)
        assert result == SlimScrew.D3_3_L50

    def test_find_coarse_thread_preset(self):
        """Should find valid coarse thread preset."""
        result = find_preset("Coarse", 3.8, 57)
        assert result == CoarseThreadScrew.D3_8_L57

    def test_find_preset_returns_none_for_unknown_slim(self):
        """Should return None for unknown slim screw size."""
        result = find_preset("Slim", 9.9, 999)
        assert result is None

    def test_find_preset_returns_none_for_unknown_coarse(self):
        """Should return None for unknown coarse thread size."""
        result = find_preset("Coarse", 9.9, 999)
        assert result is None

    def test_find_preset_returns_none_for_unknown_type(self):
        """Should return None for unknown screw type."""
        result = find_preset("Unknown", 3.3, 50)
        assert result is None


class TestDSLScrewPresetParsing:
    """Tests for DSL screw preset syntax parsing."""

    def test_parse_slim_screw_preset(self):
        """Should parse S(Slim:3.3x50) syntax."""
        dsl = """
        (base:2x4 =600)
        (target:2x4 =300)
        base -[FB<0 BT<0 S(Slim:3.3x50)]- target
        """
        model = parse_dsl(dsl)
        assert len(model.connections) == 1
        conn = list(model.connections.values())[0]
        assert isinstance(conn.type, ScrewConnection)
        assert conn.type.diameter == 3.3
        assert conn.type.length == 50.0

    def test_parse_coarse_thread_preset(self):
        """Should parse S(Coarse:3.8x57) syntax."""
        dsl = """
        (base:2x4 =600)
        (target:2x4 =300)
        base -[FB<0 BT<0 S(Coarse:3.8x57)]- target
        """
        model = parse_dsl(dsl)
        assert len(model.connections) == 1
        conn = list(model.connections.values())[0]
        assert isinstance(conn.type, ScrewConnection)
        assert conn.type.diameter == 3.8
        assert conn.type.length == 57.0

    def test_parse_numeric_screw_still_works(self):
        """Should still support S(diameter, length) numeric syntax."""
        dsl = """
        (base:2x4 =600)
        (target:2x4 =300)
        base -[FB<0 BT<0 S(4.0, 55.0)]- target
        """
        model = parse_dsl(dsl)
        assert len(model.connections) == 1
        conn = list(model.connections.values())[0]
        assert isinstance(conn.type, ScrewConnection)
        assert conn.type.diameter == 4.0
        assert conn.type.length == 55.0

    def test_reject_unknown_slim_preset(self):
        """Should reject unknown slim screw preset."""
        dsl = """
        (base:2x4 =600)
        (target:2x4 =300)
        base -[FB<0 BT<0 S(Slim:9.9x999)]- target
        """
        with pytest.raises(DSLValidationError, match="Unknown Slim screw preset"):
            parse_dsl(dsl)

    def test_reject_unknown_coarse_preset(self):
        """Should reject unknown coarse thread preset."""
        dsl = """
        (base:2x4 =600)
        (target:2x4 =300)
        base -[FB<0 BT<0 S(Coarse:9.9x999)]- target
        """
        with pytest.raises(DSLValidationError, match="Unknown Coarse screw preset"):
            parse_dsl(dsl)


class TestDSLScrewPresetIntegration:
    """Integration tests for screw preset DSL support."""

    def test_multiple_connections_with_different_presets(self):
        """Should handle multiple connections with different screw presets."""
        dsl = """
        (base:2x4 =600)
        (leg1:2x4 =300)
        (leg2:2x4 =300)

        base -[FB<0 BT<0 S(Slim:3.3x50)]- leg1
        base -[FB<100 BT<0 S(Coarse:3.8x57)]- leg2
        """
        model = parse_dsl(dsl)
        assert len(model.connections) == 2

        # First connection: Slim screw
        conn1 = model.connections[("base", "leg1")]
        assert isinstance(conn1.type, ScrewConnection)
        assert conn1.type.diameter == 3.3
        assert conn1.type.length == 50.0

        # Second connection: Coarse thread
        conn2 = model.connections[("base", "leg2")]
        assert isinstance(conn2.type, ScrewConnection)
        assert conn2.type.diameter == 3.8
        assert conn2.type.length == 57.0

    def test_mixed_numeric_and_preset_screws(self):
        """Should handle mixing numeric and preset screw specifications."""
        dsl = """
        (base:2x4 =600)
        (leg1:2x4 =300)
        (leg2:2x4 =300)

        base -[FB<0 BT<0 S(Slim:3.3x50)]- leg1
        base -[FB<100 BT<0 S(5.0, 60.0)]- leg2
        """
        model = parse_dsl(dsl)
        assert len(model.connections) == 2

        # First: preset
        conn1 = model.connections[("base", "leg1")]
        assert isinstance(conn1.type, ScrewConnection)
        assert conn1.type.diameter == 3.3

        # Second: numeric
        conn2 = model.connections[("base", "leg2")]
        assert isinstance(conn2.type, ScrewConnection)
        assert conn2.type.diameter == 5.0
        assert conn2.type.length == 60.0

    @pytest.mark.parametrize(
        "preset,expected_diameter,expected_length",
        [
            ("Slim:3.3x25", 3.3, 25.0),
            ("Slim:3.3x30", 3.3, 30.0),
            ("Slim:3.3x35", 3.3, 35.0),
            ("Slim:3.3x40", 3.3, 40.0),
            ("Slim:3.3x45", 3.3, 45.0),
            ("Slim:3.3x50", 3.3, 50.0),
            ("Slim:3.8x55", 3.8, 55.0),
            ("Slim:3.8x60", 3.8, 60.0),
            ("Slim:3.8x65", 3.8, 65.0),
            ("Slim:3.8x70", 3.8, 70.0),
            ("Slim:3.8x75", 3.8, 75.0),
            ("Slim:4.2x90", 4.2, 90.0),
            ("Coarse:3.8x25", 3.8, 25.0),
            ("Coarse:3.8x30", 3.8, 30.0),
            ("Coarse:3.8x35", 3.8, 35.0),
            ("Coarse:3.8x40", 3.8, 40.0),
            ("Coarse:3.8x45", 3.8, 45.0),
            ("Coarse:3.8x50", 3.8, 50.0),
            ("Coarse:3.8x57", 3.8, 57.0),
            ("Coarse:4.2x65", 4.2, 65.0),
            ("Coarse:4.2x75", 4.2, 75.0),
            ("Coarse:4.5x90", 4.5, 90.0),
            ("Coarse:4.5x100", 4.5, 100.0),
            ("Coarse:5.2x120", 5.2, 120.0),
        ],
    )
    def test_all_preset_sizes(self, preset, expected_diameter, expected_length):
        """Should parse all valid preset sizes."""
        dsl = f"""
        (base:2x4 =600)
        (target:2x4 =300)
        base -[FB<0 BT<0 S({preset})]- target
        """
        model = parse_dsl(dsl)
        conn = list(model.connections.values())[0]
        assert isinstance(conn.type, ScrewConnection)
        assert conn.type.diameter == expected_diameter
        assert conn.type.length == expected_length
