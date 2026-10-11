"""Tests for build123d export behaviour when build123d is unavailable.

Geometry produced with a real build123d is tested in test_build123d_geometry.py.
"""

import pytest

from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.model import Model
import nichiyou_daiku.shell.build123d_export as export_module


@pytest.fixture
def without_build123d():
    original_available = export_module.HAS_BUILD123D
    export_module.HAS_BUILD123D = False
    try:
        yield
    finally:
        export_module.HAS_BUILD123D = original_available


def test_assembly_to_build123d_requires_build123d(without_build123d):
    assembly = Assembly.of(Model.of(pieces=[], connections=[]))

    with pytest.raises(ImportError) as exc_info:
        export_module.assembly_to_build123d(assembly)

    assert "build123d is required" in str(exc_info.value)
    assert "pip install nichiyou-daiku[viz]" in str(exc_info.value)
