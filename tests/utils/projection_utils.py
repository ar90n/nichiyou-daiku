"""Utilities for exporting orthographic projections to SVG/PNG for regression testing.

This module provides functions to export top, front, and side views of
build123d Compound objects as SVG/PNG for visual regression testing.
"""

import tempfile
from pathlib import Path
from typing import IO, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from build123d import Compound

# Check if build123d is available
HAS_BUILD123D = False
try:
    from build123d import ExportSVG, Compound as Build123dCompound, LineType

    HAS_BUILD123D = True
except ImportError:
    pass

# Check if visual testing dependencies are available
HAS_VISUAL_TEST = False
try:
    import cairosvg
    from PIL import Image
    import io as pyio

    HAS_VISUAL_TEST = True
except ImportError:
    pass


def _export_projection_to_svg(
    compound: "Compound",
    output: IO[str],
    viewport_origin: tuple[float, float, float],
    viewport_up: tuple[float, float, float] = (0, 0, 1),
    *,
    svg_opts: dict | None = None,
) -> None:
    """Export a projection of a compound to SVG.

    Args:
        compound: The build123d Compound to export
        output: IO object to write SVG content to (StringIO or file)
        viewport_origin: Tuple (x, y, z) defining the viewport location
        viewport_up: Tuple (x, y, z) defining the viewport up direction
        svg_opts: Optional dict of SVG export options

    Raises:
        ImportError: If build123d is not installed
    """
    if not HAS_BUILD123D:
        raise ImportError(
            "build123d is required for projection export. "
            "Please install it with: pip install nichiyou-daiku[viz]"
        )

    # Project compound to viewport
    visible, hidden = compound.project_to_viewport(
        viewport_origin, viewport_up, look_at=(0, 0, 0)
    )

    # Calculate scale from bounding box
    max_dimension = max(
        *Build123dCompound(children=visible + hidden).bounding_box().size
    )

    # Default SVG options for deterministic output and good visibility
    default_opts = {
        "scale": 100 / max_dimension,
        "line_weight": 0.5,
        "line_color": (0, 0, 0),  # Black lines
    }
    if svg_opts:
        default_opts.update(svg_opts)

    # Create SVG exporter
    exporter = ExportSVG(**default_opts)

    # Add layers for visible and hidden edges
    # Visible: black solid lines
    exporter.add_layer("Visible", line_color=(0, 0, 0), line_weight=0.5)
    # Hidden: gray dotted lines, thinner
    exporter.add_layer(
        "Hidden",
        line_color=(128, 128, 128),
        line_type=LineType.ISO_DOT,
        line_weight=0.3,
    )

    # Add shapes to layers
    exporter.add_shape(visible, layer="Visible")
    exporter.add_shape(hidden, layer="Hidden")

    # ExportSVG.write() only accepts file paths, not IO objects
    # So we write to a temporary file and then read it back
    with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        # Write to temporary file
        exporter.write(str(tmp_path))

        # Read the file and write to output IO
        with open(tmp_path, "r", encoding="utf-8") as f:
            output.write(f.read())
    finally:
        # Clean up temporary file
        if tmp_path.exists():
            tmp_path.unlink()


def export_top_view(
    compound: "Compound",
    output: IO[str],
    *,
    svg_opts: dict | None = None,
) -> None:
    """Export top view (looking down from +Z axis) to SVG.

    Args:
        compound: The build123d Compound to export
        output: IO object to write SVG content to (StringIO or file)
        svg_opts: Optional dict of SVG export options

    Raises:
        ImportError: If build123d is not installed
    """
    _export_projection_to_svg(
        compound,
        output,
        viewport_origin=(0, 0, 1),
        viewport_up=(0, 1, 0),
        svg_opts=svg_opts,
    )


def export_front_view(
    compound: "Compound",
    output: IO[str],
    *,
    svg_opts: dict | None = None,
) -> None:
    """Export front view (looking from +Y axis) to SVG.

    Args:
        compound: The build123d Compound to export
        output: IO object to write SVG content to (StringIO or file)
        svg_opts: Optional dict of SVG export options

    Raises:
        ImportError: If build123d is not installed
    """
    _export_projection_to_svg(
        compound,
        output,
        viewport_origin=(0, 1, 0),
        viewport_up=(0, 0, 1),
        svg_opts=svg_opts,
    )


def export_side_view(
    compound: "Compound",
    output: IO[str],
    *,
    svg_opts: dict | None = None,
) -> None:
    """Export side view (looking from +X axis) to SVG.

    Args:
        compound: The build123d Compound to export
        output: IO object to write SVG content to (StringIO or file)
        svg_opts: Optional dict of SVG export options

    Raises:
        ImportError: If build123d is not installed
    """
    _export_projection_to_svg(
        compound,
        output,
        viewport_origin=(1, 0, 0),
        viewport_up=(0, 0, 1),
        svg_opts=svg_opts,
    )


def svg_to_bitmap(svg_string: str, *, dpi: int = 96) -> np.ndarray:
    """Convert SVG string to RGB bitmap (numpy array).

    Args:
        svg_string: SVG content as string
        dpi: DPI for rendering (default: 96)

    Returns:
        RGB bitmap as numpy array (height, width, 3), dtype=uint8

    Raises:
        ImportError: If cairosvg and Pillow are not installed
    """
    if not HAS_VISUAL_TEST:
        raise ImportError(
            "cairosvg and Pillow are required. "
            "Please install with: pip install nichiyou-daiku[test-visual]"
        )

    # Convert SVG to PNG bytes
    png_data = cairosvg.svg2png(
        bytestring=svg_string.encode("utf-8"), dpi=dpi, background_color="white"
    )

    # Load as PIL Image and ensure RGB mode
    img = Image.open(pyio.BytesIO(png_data))
    if img.mode != "RGB":
        rgb_img = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "RGBA":
            rgb_img.paste(img, mask=img.split()[3])
        else:
            rgb_img.paste(img)
        img = rgb_img

    # Return as numpy array
    return np.array(img, dtype=np.uint8)


def svg_to_png(svg_string: str, *, dpi: int = 96) -> bytes:
    """Convert SVG string to PNG bytes with white background.

    Args:
        svg_string: SVG content as string
        dpi: DPI for PNG rendering (default: 96)

    Returns:
        RGB PNG image data as bytes (white background, black lines)

    Raises:
        ImportError: If cairosvg is not installed
    """
    if not HAS_VISUAL_TEST:
        raise ImportError(
            "cairosvg and Pillow are required for PNG conversion. "
            "Please install with: pip install nichiyou-daiku[test-visual]"
        )

    # Convert SVG to PNG with white background
    png_data = cairosvg.svg2png(
        bytestring=svg_string.encode("utf-8"), dpi=dpi, background_color="white"
    )

    # Ensure RGB mode (remove transparency if any)
    img = Image.open(pyio.BytesIO(png_data))
    if img.mode != "RGB":
        # Create white background
        rgb_img = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "RGBA":
            # Paste with alpha channel as mask
            rgb_img.paste(img, mask=img.split()[3])
        else:
            rgb_img.paste(img)
        img = rgb_img

    # Save as RGB PNG
    output = pyio.BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


def compare_images(
    actual: np.ndarray | bytes, expected_path: Path, *, tolerance: float = 0.01
) -> tuple[bool, str]:
    """Compare image with baseline PNG.

    Args:
        actual: RGB bitmap (numpy array) or PNG bytes
        expected_path: Path to expected baseline PNG file
        tolerance: Tolerance for pixel difference (0.0 to 1.0)

    Returns:
        Tuple of (matches, message):
        - matches: True if images match within tolerance
        - message: Description of result or difference

    Raises:
        ImportError: If Pillow is not installed
        FileNotFoundError: If expected_path doesn't exist
    """
    if not HAS_VISUAL_TEST:
        raise ImportError(
            "Pillow is required for image comparison. "
            "Please install with: pip install nichiyou-daiku[test-visual]"
        )

    if not expected_path.exists():
        raise FileNotFoundError(
            f"Baseline image not found: {expected_path}\n"
            f"Run generate_baseline.py to create baseline images."
        )

    # Convert actual to numpy array if needed
    if isinstance(actual, bytes):
        actual_img = Image.open(pyio.BytesIO(actual))
        if actual_img.mode != "RGB":
            actual_img = actual_img.convert("RGB")
        actual_arr = np.array(actual_img, dtype=np.float32)
    else:
        actual_arr = actual.astype(np.float32)

    # Load expected image
    expected_img = Image.open(expected_path)
    if expected_img.mode != "RGB":
        expected_img = expected_img.convert("RGB")
    expected_arr = np.array(expected_img, dtype=np.float32)

    # Check dimensions
    if actual_arr.shape != expected_arr.shape:
        return (
            False,
            f"Image size mismatch: actual={actual_arr.shape}, "
            f"expected={expected_arr.shape}",
        )

    # Calculate normalized difference (0.0 to 1.0)
    diff = np.abs(actual_arr - expected_arr) / 255.0
    mean_diff = np.mean(diff)

    if mean_diff <= tolerance:
        return (True, f"Images match (diff={mean_diff:.6f}, tolerance={tolerance})")
    else:
        return (
            False,
            f"Images differ too much: diff={mean_diff:.6f}, tolerance={tolerance}",
        )
