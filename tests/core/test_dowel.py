"""Tests for dowel module."""

import pytest

from nichiyou_daiku.core.dowel import (
    DowelSpec,
    Dowel,
    as_spec,
    find_preset,
)


class TestDowelSpec:
    """Test DowelSpec class."""

    def test_should_create_dowel_spec(self):
        """Should create DowelSpec with diameter and length."""
        spec = DowelSpec(diameter=8.0, length=30.0)

        assert spec.diameter == 8.0
        assert spec.length == 30.0

    def test_should_be_immutable(self):
        """Should not allow modification after creation."""
        spec = DowelSpec(diameter=8.0, length=30.0)

        with pytest.raises(Exception):  # Pydantic raises ValidationError
            spec.diameter = 10.0  # type: ignore


class TestDowel:
    """Test Dowel enum."""

    def test_should_have_standard_sizes(self):
        """Should define standard dowel sizes."""
        assert Dowel.D6_L25.value == "6x25"
        assert Dowel.D6_L30.value == "6x30"
        assert Dowel.D8_L25.value == "8x25"
        assert Dowel.D8_L30.value == "8x30"
        assert Dowel.D8_L40.value == "8x40"
        assert Dowel.D10_L30.value == "10x30"
        assert Dowel.D10_L40.value == "10x40"
        assert Dowel.D12_L40.value == "12x40"

    def test_of_should_parse_valid_size(self):
        """Should parse valid size string to enum."""
        assert Dowel.of("8x30") == Dowel.D8_L30
        assert Dowel.of("6x25") == Dowel.D6_L25
        assert Dowel.of("12x40") == Dowel.D12_L40

    def test_of_should_raise_for_invalid_size(self):
        """Should raise ValueError for unknown size."""
        with pytest.raises(ValueError, match="Unknown Dowel"):
            Dowel.of("9x99")


class TestAsSpec:
    """Test as_spec function."""

    @pytest.mark.parametrize(
        "preset,expected_diameter,expected_length",
        [
            (Dowel.D6_L25, 6.0, 25.0),
            (Dowel.D6_L30, 6.0, 30.0),
            (Dowel.D8_L25, 8.0, 25.0),
            (Dowel.D8_L30, 8.0, 30.0),
            (Dowel.D8_L40, 8.0, 40.0),
            (Dowel.D10_L30, 10.0, 30.0),
            (Dowel.D10_L40, 10.0, 40.0),
            (Dowel.D12_L40, 12.0, 40.0),
        ],
    )
    def test_should_convert_preset_to_spec(
        self, preset: Dowel, expected_diameter: float, expected_length: float
    ):
        """Should correctly convert preset to spec."""
        spec = as_spec(preset)
        assert spec.diameter == expected_diameter
        assert spec.length == expected_length


class TestFindPreset:
    """Test find_preset function."""

    def test_should_find_existing_preset(self):
        """Should return preset for valid dimensions."""
        preset = find_preset(8, 30)

        assert preset == Dowel.D8_L30

    def test_should_return_none_for_invalid_dimensions(self):
        """Should return None for unknown dimensions."""
        preset = find_preset(9, 99)

        assert preset is None

    def test_should_handle_float_dimensions(self):
        """Should handle float input by converting to int."""
        preset = find_preset(8.0, 30.0)

        assert preset == Dowel.D8_L30

    @pytest.mark.parametrize(
        "diameter,length,expected",
        [
            (6, 25, Dowel.D6_L25),
            (6, 30, Dowel.D6_L30),
            (8, 25, Dowel.D8_L25),
            (8, 30, Dowel.D8_L30),
            (8, 40, Dowel.D8_L40),
            (10, 30, Dowel.D10_L30),
            (10, 40, Dowel.D10_L40),
            (12, 40, Dowel.D12_L40),
        ],
    )
    def test_should_find_preset_by_dimensions(
        self, diameter: float, length: float, expected: Dowel
    ):
        """Should find preset by dimensions."""
        preset = find_preset(diameter, length)
        assert preset == expected
