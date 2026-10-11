"""Export DSL files to 3D formats (STL, STEP)."""

import sys
from pathlib import Path
from typing import Optional

import click

from nichiyou_daiku.cli.utils import (
    CliEcho,
    convert_assembly_to_build123d,
    create_assembly_from_model,
    ensure_build123d_available,
    ensure_not_overwriting_input,
    parse_dsl_to_model,
    read_dsl_file,
    require_output_for_stdin,
)


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


def resolve_export_target(
    input_file: Path, output: Optional[Path], format: Optional[str]
) -> tuple[Path, str]:
    """Determine the output path and normalized format ('stl' or 'step').

    Raises:
        click.ClickException: If neither is given, the format cannot be
            detected, or the -o extension contradicts -f
    """
    if format is None:
        if output is None:
            raise click.ClickException(
                "Either output file (-o) or format (-f) must be specified."
            )
        detected = detect_format_from_extension(output.suffix)
        if detected is None:
            raise click.ClickException(
                f"Cannot detect format from extension '{output.suffix}'. "
                "Please specify format with -f option."
            )
        return output, detected

    requested = "step" if format == "stp" else format
    if output is None:
        return input_file.with_suffix(f".{format}"), requested

    detected = detect_format_from_extension(output.suffix)
    if detected is not None and detected != requested:
        raise click.ClickException(
            f"Output extension '{output.suffix}' does not match format '{format}'."
        )
    return output, requested


@click.command()
@click.argument("input_file", type=str)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    help=(
        "Output file path. If not specified, uses the input filename with the "
        "format's extension (required when reading from stdin). Never "
        "overwrites the input file."
    ),
)
@click.option(
    "-f",
    "--format",
    type=click.Choice(["stl", "step", "stp"], case_sensitive=False),
    help=(
        "Export format. If not specified, detected from the output file "
        "extension (.stl, .step, .stp). An error is raised if it contradicts "
        "the output extension."
    ),
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
    input_file: str,
    output: Optional[Path],
    format: Optional[str],
    fillet_radius: float,
) -> None:
    """Export DSL file to 3D format (STL or STEP).

    INPUT_FILE: Path to .nd file or '-' for stdin

    \b
    Examples:
        nichiyou-daiku export furniture.nd -f stl
        nichiyou-daiku export table.nd -o table.step
        nichiyou-daiku export chair.nd --fillet-radius 10
    """
    echo = CliEcho(ctx)

    # Check if build123d is available
    ensure_build123d_available(echo)

    require_output_for_stdin(input_file, output)
    output_path, export_format = resolve_export_target(Path(input_file), output, format)
    ensure_not_overwriting_input(input_file, output_path)

    # Read and parse DSL file
    dsl_content = read_dsl_file(input_file)
    model = parse_dsl_to_model(dsl_content, echo)
    assembly = create_assembly_from_model(model, echo)

    # Convert to build123d
    compound = convert_assembly_to_build123d(
        assembly, echo, fillet_radius=fillet_radius
    )

    # Export to file
    try:
        # Import build123d export functions
        from build123d import export_stl, export_step

        if export_format == "stl":
            # export_stl reports failure via its return value instead of raising
            written = export_stl(compound, str(output_path))
        else:
            written = export_step(compound, str(output_path))
    except Exception as e:
        echo.exception(f"Error exporting file: {e}")
        sys.exit(1)

    if not written or not output_path.is_file():
        echo.error(f"Error exporting file: could not write {output_path}")
        sys.exit(1)

    echo.info(f"Successfully exported to: {output_path}")
