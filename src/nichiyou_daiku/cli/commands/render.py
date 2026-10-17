"""Render command: a labelled four-view check image (PNG)."""

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
    import_viz_module,
    parse_dsl_to_model,
    read_dsl_file,
    require_output_for_stdin,
)


@click.command()
@click.argument("input_file", type=str)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    help="Output PNG path (default: <input>.png, required for stdin).",
)
@click.option(
    "--size",
    type=click.IntRange(min=400),
    default=1400,
    show_default=True,
    help="Width and height of the image in pixels.",
)
@click.option(
    "--fillet-radius",
    type=float,
    default=5.0,
    help="Fillet radius in mm (default: 5.0, use 0 to disable)",
)
@click.pass_context
def render(
    ctx: click.Context,
    input_file: str,
    output: Optional[Path],
    size: int,
    fillet_radius: float,
) -> None:
    """Render a check image (PNG): four labelled views of the model.

    INPUT_FILE: Path to .nd file or '-' for stdin

    The views look from +z, +y, -x and -x +y +z (the top, the front, the
    right side and an isometric view; the furniture's front faces +y), in
    the axes of the first piece declared (see validate --json). Each
    piece's ID is written where the viewer can see its center; pieces
    hidden in every view are listed in the note.

    \b
    Examples:
        nichiyou-daiku render table.nd
        nichiyou-daiku render table.nd -o check.png --size 1000
    """
    echo = CliEcho(ctx)

    ensure_build123d_available(echo)
    render_sheet = import_viz_module("nichiyou_daiku.shell.render", echo).render_sheet

    require_output_for_stdin(input_file, output)
    output_path = output or Path(input_file).with_suffix(".png")
    ensure_not_overwriting_input(input_file, output_path)
    title = output_path.name if input_file == "-" else Path(input_file).name

    model = parse_dsl_to_model(read_dsl_file(input_file), echo)
    assembly = create_assembly_from_model(model, echo)
    part = convert_assembly_to_build123d(assembly, echo, fillet_radius=fillet_radius)

    try:
        sheet = render_sheet(part, assembly, title=title, size=size)
        output_path.write_bytes(sheet.png())
    except Exception as e:
        echo.exception(f"Error rendering the image: {e}")
        sys.exit(1)

    echo.info(f"Successfully rendered: {output_path}")
