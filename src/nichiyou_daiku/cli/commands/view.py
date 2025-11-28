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


def try_ocp_vscode_viewer(compound, echo: CliEcho) -> bool:
    """Try to display model using OCP VSCode viewer.

    Args:
        compound: The 3D model to display
        echo: CliEcho instance for output

    Returns:
        True if viewer was successfully used, False otherwise
    """
    try:
        from ocp_vscode import show

        echo.echo("Displaying in VS Code OCP CAD Viewer...")
        show(compound)
        return True
    except ImportError:
        return False


def try_jupyter_cadquery_viewer(compound, echo: CliEcho) -> bool:
    """Try to display model using Jupyter CadQuery viewer.

    Args:
        compound: The 3D model to display
        echo: CliEcho instance for output

    Returns:
        True if viewer was successfully used, False otherwise
    """
    try:
        from jupyter_cadquery import show as jcq_show

        echo.echo("Displaying in Jupyter CadQuery...")
        jcq_show(compound)
        return True
    except ImportError:
        return False


@click.command()
@click.argument("file", type=str)
@click.option(
    "--fillet-radius", type=float, default=3.0, help="Fillet radius for edges (mm)"
)
@click.pass_context
def view(ctx: click.Context, file: str, fillet_radius: float) -> None:
    """Display 3D model from DSL file.

    FILE: Path to .nd file or '-' for stdin
    """
    echo = CliEcho(ctx)

    # Check build123d availability first
    ensure_build123d_available(echo)

    # Read DSL content
    try:
        dsl_content = read_dsl_file(file)
    except click.ClickException as e:
        echo.error(f"Error: {e}")
        sys.exit(1)

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
