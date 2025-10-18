"""Visual regression tests for 3D projections.

These tests compare generated PNG projections against baseline images
to detect unintended changes in the 3D model generation or rendering.
"""

import io
import pytest
from pathlib import Path

from tests.utils.projection_utils import (
    HAS_BUILD123D,
    HAS_VISUAL_TEST,
    export_top_view,
    export_front_view,
    export_side_view,
    svg_to_bitmap,
    compare_images,
)
from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.shell import assembly_to_build123d


# Fixture directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.skipif(
    not HAS_BUILD123D, reason="build123d not installed (install with viz extras)"
)
@pytest.mark.skipif(
    not HAS_VISUAL_TEST,
    reason="Visual test dependencies not installed (install with test-visual extras)",
)
@pytest.mark.parametrize(
    "model_name,view_name,export_func",
    [
        ("corner_angle", "top_view", export_top_view),
        ("corner_angle", "front_view", export_front_view),
        ("corner_angle", "side_view", export_side_view),
        ("simple_table", "top_view", export_top_view),
        ("simple_table", "front_view", export_front_view),
        ("simple_table", "side_view", export_side_view),
    ],
)
def test_projection_matches_baseline(model_name, view_name, export_func):
    """Test that projection matches baseline PNG image.

    This test:
    1. Loads the .nd model file
    2. Generates a 3D assembly
    3. Exports the specified view as SVG
    4. Converts SVG to PNG
    5. Compares PNG with baseline image

    If the test fails, it means either:
    - The 3D geometry has changed (check if intentional)
    - The rendering has changed (check build123d version)
    - The baseline needs to be regenerated
    """
    # 1. Load model
    nd_path = FIXTURES_DIR / model_name / "model.nd"
    assert nd_path.exists(), f"Model file not found: {nd_path}"

    model = parse_dsl(nd_path.read_text())

    # 2. Generate 3D assembly
    assembly = Assembly.of(model)
    compound = assembly_to_build123d(assembly, fillet_radius=0.0)

    # 3. Export view as SVG
    svg_output = io.StringIO()
    export_func(compound, svg_output)

    # 4. Convert to bitmap (no PNG encoding)
    actual_bitmap = svg_to_bitmap(svg_output.getvalue())

    # 5. Compare with baseline
    baseline_path = FIXTURES_DIR / model_name / f"{view_name}.png"

    matches, message = compare_images(actual_bitmap, baseline_path, tolerance=0.01)

    assert matches, (
        f"Projection does not match baseline: {message}\n"
        f"Model: {model_name}, View: {view_name}\n"
        f"Baseline: {baseline_path}\n"
        f"To update baseline, run: uv run python tests/regression/generate_baseline.py"
    )
