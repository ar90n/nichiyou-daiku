"""Generate technical drawing (PDF) from DSL file."""

import sys
import tempfile
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


@click.command()
@click.argument("input_file", type=str)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    help=(
        "Output file path (default: <input>.pdf, required for stdin). "
        "Use a .svg extension to write SVG instead of PDF."
    ),
)
@click.option(
    "--title",
    type=str,
    help="Drawing title (default: input filename)",
)
@click.option(
    "--drawing-number",
    type=str,
    default="ND-1",
    help="Drawing number (default: ND-1)",
)
@click.option(
    "--designed-by",
    type=str,
    default="nichiyou-daiku",
    help="Designer name (default: nichiyou-daiku)",
)
@click.option(
    "--fillet-radius",
    type=float,
    default=5.0,
    help="Fillet radius in mm (default: 5.0, use 0 to disable)",
)
@click.option(
    "--page-size",
    type=click.Choice(["A4", "A3", "A2", "A1"], case_sensitive=False),
    default="A3",
    help="Drawing page size (default: A3)",
)
@click.pass_context
def drawing(
    ctx: click.Context,
    input_file: str,
    output: Optional[Path],
    title: Optional[str],
    drawing_number: str,
    designed_by: str,
    fillet_radius: float,
    page_size: str,
) -> None:
    """Generate technical drawing (PDF) with orthographic views.

    INPUT_FILE: Path to .nd file or '-' for stdin

    Creates technical drawing with:
    - Top view (plan)
    - Front view (elevation)
    - Side view (right side)
    - Isometric view

    \b
    Examples:
        nichiyou-daiku drawing furniture.nd
        nichiyou-daiku drawing table.nd -o table_drawing.pdf
        nichiyou-daiku drawing chair.nd --title "Chair Design"
        nichiyou-daiku drawing shelf.nd --page-size A2
    """
    echo = CliEcho(ctx)

    ensure_build123d_available(echo)
    try:
        import cairosvg

        from nichiyou_daiku.shell.drawing import technical_drawing
    except ImportError as e:
        echo.error(
            f"Error importing dependencies: {e}\n"
            "Please install with: uv add nichiyou-daiku[viz]"
        )
        sys.exit(1)

    # Determine output path and title
    require_output_for_stdin(input_file, output)
    output_path = output or Path(input_file).with_suffix(".pdf")
    ensure_not_overwriting_input(input_file, output_path)
    write_svg_only = output_path.suffix.lower() == ".svg"
    source_stem = output_path.stem if input_file == "-" else Path(input_file).stem

    dsl_content = read_dsl_file(input_file)
    model = parse_dsl_to_model(dsl_content, echo)
    assembly = create_assembly_from_model(model, echo)
    compound = convert_assembly_to_build123d(
        assembly, echo, fillet_radius=fillet_radius
    )

    try:
        exporter = technical_drawing(
            compound,
            title=title or source_stem,
            drawing_number=drawing_number,
            designed_by=designed_by,
            page_size=page_size,
        )
    except Exception as e:
        echo.exception(f"Error creating drawing: {e}")
        sys.exit(1)

    if write_svg_only:
        try:
            exporter.write(str(output_path))
        except Exception as e:
            echo.exception(f"Error exporting SVG: {e}")
            sys.exit(1)
    else:
        # Render via a private temp SVG so files next to the output are untouched
        with tempfile.TemporaryDirectory() as tmp_dir:
            svg_path = Path(tmp_dir) / "drawing.svg"
            try:
                exporter.write(str(svg_path))
                cairosvg.svg2pdf(url=str(svg_path), write_to=str(output_path))
            except Exception as e:
                echo.exception(f"Error converting to PDF: {e}")
                sys.exit(1)

    echo.info(f"Successfully created technical drawing: {output_path}")
