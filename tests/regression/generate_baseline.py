#!/usr/bin/env python
"""Generate baseline PNG images for visual regression tests.

This script reads .nd model files from fixtures/ and generates
PNG projections (top, front, side) for each model.

Usage:
    uv run python tests/regression/generate_baseline.py
"""

import io
import sys
from pathlib import Path

# Add tests to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.utils.projection_utils import (
    HAS_BUILD123D,
    HAS_VISUAL_TEST,
    export_top_view,
    export_front_view,
    export_side_view,
    svg_to_png,
)
from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.shell import assembly_to_build123d


def generate_baseline_for_model(model_dir: Path):
    """Generate baseline images for a single model.

    Args:
        model_dir: Directory containing model.nd file
    """
    nd_file = model_dir / "model.nd"
    if not nd_file.exists():
        print(f"⚠️  Skipping {model_dir.name}: model.nd not found")
        return

    print(f"📝 Processing {model_dir.name}...")

    # Parse model
    try:
        model = parse_dsl(nd_file.read_text())
    except Exception as e:
        print(f"❌ Failed to parse {model_dir.name}: {e}")
        return

    # Create assembly
    try:
        assembly = Assembly.of(model)
        compound = assembly_to_build123d(assembly, fillet_radius=0.0)
    except Exception as e:
        print(f"❌ Failed to create assembly for {model_dir.name}: {e}")
        return

    # Generate each view
    views = [
        ("top_view", export_top_view),
        ("front_view", export_front_view),
        ("side_view", export_side_view),
    ]

    for view_name, export_func in views:
        try:
            # Generate SVG
            svg_output = io.StringIO()
            export_func(compound, svg_output)

            # Convert to PNG
            png_data = svg_to_png(svg_output.getvalue())

            # Save PNG
            output_path = model_dir / f"{view_name}.png"
            output_path.write_bytes(png_data)
            print(f"  ✅ {view_name}.png")

        except Exception as e:
            print(f"  ❌ Failed to generate {view_name}: {e}")


def main():
    """Generate all baseline images."""
    if not HAS_BUILD123D:
        print("❌ build123d is not installed.")
        print("   Install with: uv sync --all-extras")
        sys.exit(1)

    if not HAS_VISUAL_TEST:
        print("❌ Visual test dependencies are not installed.")
        print("   Install with: uv pip install cairosvg Pillow")
        sys.exit(1)

    # Find all model directories
    fixtures_dir = Path(__file__).parent / "fixtures"
    if not fixtures_dir.exists():
        print(f"❌ Fixtures directory not found: {fixtures_dir}")
        sys.exit(1)

    model_dirs = [d for d in fixtures_dir.iterdir() if d.is_dir()]
    if not model_dirs:
        print(f"❌ No model directories found in {fixtures_dir}")
        sys.exit(1)

    print(f"🚀 Generating baseline images for {len(model_dirs)} models...\n")

    for model_dir in sorted(model_dirs):
        generate_baseline_for_model(model_dir)

    print("\n✅ Done!")


if __name__ == "__main__":
    main()
