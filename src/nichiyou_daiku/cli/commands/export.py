"""Export DSL files to 3D formats (STL, STEP)."""

import sys
from pathlib import Path
from typing import Optional

import click

from nichiyou_daiku.cli.utils import read_dsl_file, CliEcho
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.shell.build123d_export import assembly_to_build123d, HAS_BUILD123D


def detect_format_from_extension(suffix: str) -> Optional[str]:
    """Detect export format from file extension.

    Args:
        suffix: File extension (e.g., '.stl', '.step')

    Returns:
        Format string ('stl' or 'step') or None if unknown
    """
    suffix_lower = suffix.lower()
    if suffix_lower == ".stl":
        return "stl"
    elif suffix_lower in [".step", ".stp"]:
        return "step"
    return None


@click.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    help="Output file path. If not specified, uses input filename with new extension.",
)
@click.option(
    "-f",
    "--format",
    type=click.Choice(["stl", "step", "stp"], case_sensitive=False),
    help="Export format. If not specified, detected from output file extension.",
)
@click.option(
    "--fillet-radius",
    type=float,
    default=5.0,
    help="Fillet radius in mm for edges (default: 5.0, use 0 to disable).",
)
@click.pass_context
def export(
    ctx: click.Context,
    input_file: Path,
    output: Optional[Path],
    format: Optional[str],
    fillet_radius: float,
) -> None:
    """Export DSL file to 3D format (STL or STEP).

    \b
    Examples:
        nichiyou-daiku export furniture.nd -f stl
        nichiyou-daiku export table.nd -o table.step
        nichiyou-daiku export chair.nd --fillet-radius 10
    """
    echo = CliEcho(ctx)

    # Check if build123d is available
    if not HAS_BUILD123D:
        echo.error(
            "Error: build123d is required for 3D export.\n"
            "Please install it with: uv add nichiyou-daiku[viz]"
        )
        sys.exit(1)

    # Determine output format and filename
    if format and output:
        # Both specified, use as-is
        output_path = output
        export_format = format.lower()
    elif output and not format:
        # Output specified, detect format from extension
        output_path = output
        export_format = detect_format_from_extension(output.suffix)
        if export_format is None:
            echo.error(
                f"Error: Cannot detect format from extension '{output.suffix}'. "
                "Please specify format with -f option."
            )
            sys.exit(1)
    elif format and not output:
        # Format specified, generate output filename
        export_format = format.lower()
        if export_format == "stp":
            export_format = "step"  # Normalize stp to step
            ext = ".stp"
        else:
            ext = f".{export_format}"
        output_path = input_file.with_suffix(ext)
    else:
        # Neither specified
        echo.error("Error: Either output file (-o) or format (-f) must be specified.")
        sys.exit(1)

    # Normalize format
    if export_format == "stp":
        export_format = "step"

    # Read and parse DSL file
    try:
        dsl_content = read_dsl_file(str(input_file))
        model = parse_dsl(dsl_content)
    except Exception as e:
        echo.error(f"Error parsing DSL file: {e}")
        sys.exit(1)

    # Create assembly
    try:
        assembly = Assembly.of(model)
    except Exception as e:
        echo.error(f"Error creating assembly: {e}")
        sys.exit(1)

    # Convert to build123d
    try:
        compound = assembly_to_build123d(assembly, fillet_radius=fillet_radius)
    except Exception as e:
        echo.error(f"Error converting to 3D model: {e}")
        sys.exit(1)

    # Export to file
    try:
        # Import build123d export functions
        from build123d import export_stl, export_step

        if export_format == "stl":
            export_stl(compound, str(output_path))
        elif export_format == "step":
            export_step(compound, str(output_path))
        else:
            echo.error(f"Error: Unsupported format '{export_format}'")
            sys.exit(1)

        echo.echo(f"Successfully exported to: {output_path}")
    except Exception as e:
        echo.error(f"Error exporting file: {e}")
        sys.exit(1)
