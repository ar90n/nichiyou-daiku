"""Steps command: assembly instructions, a Markdown page and one image per step."""

import sys
from pathlib import Path
from typing import Optional

import click

from nichiyou_daiku.cli.utils import (
    CliEcho,
    convert_assembly_to_build123d,
    create_assembly_from_model,
    ensure_build123d_available,
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
    help=(
        "Directory for steps.md and the step images "
        "(default: <input>-steps, required for stdin)."
    ),
)
@click.option(
    "--size",
    type=click.IntRange(min=400),
    default=1600,
    show_default=True,
    help="Width of each step image in pixels.",
)
@click.option(
    "--fillet-radius",
    type=float,
    default=5.0,
    help="Fillet radius in mm (default: 5.0, use 0 to disable)",
)
@click.pass_context
def steps(
    ctx: click.Context,
    input_file: str,
    output: Optional[Path],
    size: int,
    fillet_radius: float,
) -> None:
    """Write assembly instructions: steps.md and one image per step.

    INPUT_FILE: Path to .nd file or '-' for stdin

    The steps come from the file's steps block; without one, each step adds
    one piece. Each image shows what is built so far in grey and the step's
    pieces in black, beside a view dimensioning where they go.

    \b
    Examples:
        nichiyou-daiku steps shelf.nd
        nichiyou-daiku steps shelf.nd -o instructions --size 1200
    """
    echo = CliEcho(ctx)

    ensure_build123d_available(echo)
    write_instructions = import_viz_module(
        "nichiyou_daiku.shell.instructions", echo
    ).write_instructions

    require_output_for_stdin(input_file, output)
    directory = output or Path(input_file).with_name(f"{Path(input_file).stem}-steps")
    if directory.exists() and not directory.is_dir():
        echo.error(f"{directory} is a file; give -o a directory for the steps")
        sys.exit(1)
    title = directory.name if input_file == "-" else Path(input_file).stem

    model = parse_dsl_to_model(read_dsl_file(input_file), echo)
    assembly = create_assembly_from_model(model, echo)
    part = convert_assembly_to_build123d(assembly, echo, fillet_radius=fillet_radius)

    try:
        result = write_instructions(assembly, part, directory, title, size=size)
    except Exception as e:
        echo.exception(f"Error writing the steps: {e}")
        sys.exit(1)

    if result.hint:
        echo.info(result.hint)
    for message in result.crowded:
        echo.info(click.style(f"Warning: {message}", fg="yellow"))
    images = len(result.files) - 1
    echo.info(
        f"Successfully wrote steps.md and {images} step "
        f"image{'' if images == 1 else 's'} to {directory}"
    )
