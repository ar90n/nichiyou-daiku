"""Tests for screw module."""

import pytest

from nichiyou_daiku.core.screw import (
    ScrewSpec,
    SlimScrew,
    CoarseThreadScrew,
    ScrewPreset,
    as_spec,
)


class TestScrewSpec:
    """ScrewSpec model tests."""

    def test_create_screw_spec(self):
        """ScrewSpec should be created with diameter and length."""
        spec = ScrewSpec(diameter=3.5, length=50.0)
        assert spec.diameter == 3.5
        assert spec.length == 50.0

    def test_screw_spec_is_frozen(self):
        """ScrewSpec should be immutable."""
        spec = ScrewSpec(diameter=3.5, length=50.0)
        with pytest.raises(Exception):  # ValidationError or AttributeError
            spec.diameter = 4.0  # type: ignore


class TestSlimScrew:
    """SlimScrew enum tests."""

    def test_slim_screw_values(self):
        """SlimScrew should have correct string values."""
        assert SlimScrew.D3_3_L25.value == "3.3x25"
        assert SlimScrew.D3_3_L50.value == "3.3x50"
        assert SlimScrew.D3_8_L75.value == "3.8x75"
        assert SlimScrew.D4_2_L90.value == "4.2x90"

    def test_slim_screw_of(self):
        """SlimScrew.of should parse string values."""
        assert SlimScrew.of("3.3x50") == SlimScrew.D3_3_L50
        assert SlimScrew.of("3.8x65") == SlimScrew.D3_8_L65

    def test_slim_screw_of_invalid_raises(self):
        """SlimScrew.of should raise ValueError for unknown sizes."""
        with pytest.raises(ValueError, match="Unknown slim screw"):
            SlimScrew.of("5.0x100")

    def test_slim_screw_count(self):
        """SlimScrew should have 12 sizes."""
        assert len(SlimScrew) == 12


class TestCoarseThreadScrew:
    """CoarseThreadScrew enum tests."""

    def test_coarse_thread_values(self):
        """CoarseThreadScrew should have correct string values."""
        assert CoarseThreadScrew.D3_8_L25.value == "3.8x25"
        assert CoarseThreadScrew.D3_8_L57.value == "3.8x57"
        assert CoarseThreadScrew.D4_5_L100.value == "4.5x100"
        assert CoarseThreadScrew.D5_2_L120.value == "5.2x120"

    def test_coarse_thread_of(self):
        """CoarseThreadScrew.of should parse string values."""
        assert CoarseThreadScrew.of("3.8x57") == CoarseThreadScrew.D3_8_L57
        assert CoarseThreadScrew.of("4.5x90") == CoarseThreadScrew.D4_5_L90

    def test_coarse_thread_of_invalid_raises(self):
        """CoarseThreadScrew.of should raise ValueError for unknown sizes."""
        with pytest.raises(ValueError, match="Unknown coarse thread"):
            CoarseThreadScrew.of("6.0x150")

    def test_coarse_thread_count(self):
        """CoarseThreadScrew should have 12 sizes."""
        assert len(CoarseThreadScrew) == 12


class TestGetSpec:
    """get_spec function tests."""

    def test_get_spec_slim_screw(self):
        """get_spec should return correct spec for SlimScrew."""
        spec = as_spec(SlimScrew.D3_3_L50)
        assert spec.diameter == 3.3
        assert spec.length == 50.0

    def test_get_spec_coarse_thread(self):
        """get_spec should return correct spec for CoarseThreadScrew."""
        spec = as_spec(CoarseThreadScrew.D3_8_L57)
        assert spec.diameter == 3.8
        assert spec.length == 57.0

    def test_get_spec_all_slim_screws(self):
        """get_spec should work for all SlimScrew variants."""
        for screw in SlimScrew:
            spec = as_spec(screw)
            assert spec.diameter > 0
            assert spec.length > 0

    def test_get_spec_all_coarse_threads(self):
        """get_spec should work for all CoarseThreadScrew variants."""
        for screw in CoarseThreadScrew:
            spec = as_spec(screw)
            assert spec.diameter > 0
            assert spec.length > 0

    def test_get_spec_returns_screw_spec(self):
        """get_spec should return ScrewSpec instance."""
        spec = as_spec(SlimScrew.D3_3_L25)
        assert isinstance(spec, ScrewSpec)


class TestScrewPresetType:
    """ScrewPreset type alias tests."""

    def test_slim_screw_is_screw_preset(self):
        """SlimScrew should be a valid ScrewPreset."""
        screw: ScrewPreset = SlimScrew.D3_3_L50
        assert isinstance(screw, SlimScrew)

    def test_coarse_thread_is_screw_preset(self):
        """CoarseThreadScrew should be a valid ScrewPreset."""
        screw: ScrewPreset = CoarseThreadScrew.D3_8_L57
        assert isinstance(screw, CoarseThreadScrew)
