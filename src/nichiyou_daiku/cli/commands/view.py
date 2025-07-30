"""View command for displaying 3D models from DSL files."""

import sys

import click

from nichiyou_daiku.cli.utils import read_dsl_file, CliEcho
from nichiyou_daiku.dsl import (
    parse_dsl,
    DSLSyntaxError,
    DSLSemanticError,
    DSLValidationError,
)
from nichiyou_daiku.core.assembly import Assembly


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

    # Read DSL content
    try:
        dsl_content = read_dsl_file(file)
    except click.ClickException as e:
        echo.error(f"Error: {e}")
        sys.exit(1)

    # Parse DSL
    try:
        echo.verbose("Parsing DSL file...")

        model = parse_dsl(dsl_content)

        echo.verbose(
            f"Found {len(model.pieces)} pieces and {len(model.connections)} connections"
        )

    except (DSLSyntaxError, DSLSemanticError, DSLValidationError) as e:
        echo.error(f"DSL Error: {e}")
        sys.exit(1)
    except Exception as e:
        echo.error(f"Unexpected error parsing DSL: {e}")
        sys.exit(1)

    # Create assembly
    try:
        echo.verbose("Creating 3D assembly...")

        assembly = Assembly.of(model)

    except Exception as e:
        echo.error(f"Error creating assembly: {e}")
        sys.exit(1)

    # Try to display with build123d
    try:
        from nichiyou_daiku.shell import assembly_to_build123d

        echo.verbose("Converting to build123d model...")

        compound = assembly_to_build123d(assembly, fillet_radius=fillet_radius)

        # Try different viewers
        viewer_found = False

        # Try ocp_vscode first
        try:
            from ocp_vscode import show

            echo.echo("Displaying in VS Code OCP CAD Viewer...")
            show(compound)
            viewer_found = True
        except ImportError:
            pass

        # Try jupyter_cadquery if available
        if not viewer_found:
            try:
                from jupyter_cadquery import show as jcq_show

                echo.echo("Displaying in Jupyter CadQuery...")
                jcq_show(compound)
                viewer_found = True
            except ImportError:
                pass

        if not viewer_found:
            echo.error("No 3D viewer found. Install ocp-vscode or jupyter-cadquery.")
            echo.error("\nTo install ocp-vscode:")
            echo.error("  uv add ocp-vscode")
            sys.exit(1)

    except ImportError:
        echo.error("build123d is required for 3D visualization.")
        echo.error("\nTo install visualization dependencies:")
        echo.error("  uv sync --all-extras")
        sys.exit(1)
    except Exception as e:
        echo.error(f"Error displaying model: {e}")
        sys.exit(1)
