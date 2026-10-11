"""View command for displaying 3D models from DSL files."""

import sys

import click

from nichiyou_daiku.cli.utils import (
    CliEcho,
    convert_assembly_to_build123d,
    create_assembly_from_model,
    ensure_build123d_available,
    parse_dsl_to_model,
    read_dsl_file,
)


def show_or_exit(show, compound, viewer_name: str, echo: CliEcho) -> None:
    """Display model with an installed viewer, exiting with 1 if it fails.

    Args:
        show: The viewer's show function
        compound: The 3D model to display
        viewer_name: Human-readable viewer name for messages
        echo: CliEcho instance for output

    Raises:
        SystemExit: If the viewer fails (e.g. it is not running)
    """
    echo.info(f"Displaying in {viewer_name}...")
    try:
        show(compound)
    except Exception as e:
        echo.exception(
            f"Error: Could not display model in {viewer_name}: {e}\n"
            f"Make sure {viewer_name} is running."
        )
        sys.exit(1)


def try_ocp_vscode_viewer(compound, echo: CliEcho) -> bool:
    """Try to display model using OCP VSCode viewer.

    Args:
        compound: The 3D model to display
        echo: CliEcho instance for output

    Returns:
        True if viewer was successfully used, False if it is not installed
    """
    try:
        from ocp_vscode import show
    except ImportError:
        return False

    show_or_exit(show, compound, "VS Code OCP CAD Viewer", echo)
    return True


def try_jupyter_cadquery_viewer(compound, echo: CliEcho) -> bool:
    """Try to display model using Jupyter CadQuery viewer.

    Args:
        compound: The 3D model to display
        echo: CliEcho instance for output

    Returns:
        True if viewer was successfully used, False if it is not installed
    """
    try:
        from jupyter_cadquery import show as jcq_show
    except ImportError:
        return False

    show_or_exit(jcq_show, compound, "Jupyter CadQuery", echo)
    return True


@click.command()
@click.argument("file", type=str)
@click.option(
    "--fillet-radius",
    type=float,
    default=5.0,
    help="Fillet radius in mm for edges (default: 5.0, use 0 to disable).",
)
@click.pass_context
def view(ctx: click.Context, file: str, fillet_radius: float) -> None:
    """Display 3D model from DSL file.

    FILE: Path to .nd file or '-' for stdin
    """
    echo = CliEcho(ctx)

    # Check build123d availability first
    ensure_build123d_available(echo)

    dsl_content = read_dsl_file(file)

    # Parse DSL and create assembly
    model = parse_dsl_to_model(dsl_content, echo)
    assembly = create_assembly_from_model(model, echo)

    # Convert to build123d model
    compound = convert_assembly_to_build123d(
        assembly, echo, fillet_radius=fillet_radius
    )

    # Try different viewers
    viewer_found = try_ocp_vscode_viewer(compound, echo)

    if not viewer_found:
        viewer_found = try_jupyter_cadquery_viewer(compound, echo)

    if not viewer_found:
        echo.error("No 3D viewer found. Install ocp-vscode or jupyter-cadquery.")
        echo.error("\nTo install ocp-vscode:")
        echo.error("  uv add ocp-vscode")
        sys.exit(1)
