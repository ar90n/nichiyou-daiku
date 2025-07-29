"""View command for displaying 3D models from DSL files."""

import sys

import click

from nichiyou_daiku.cli.utils import read_dsl_file
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
    quiet = ctx.obj.get("quiet", False)
    verbose = ctx.obj.get("verbose", False)

    # Read DSL content
    try:
        dsl_content = read_dsl_file(file)
    except click.ClickException as e:
        if not quiet:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Parse DSL
    try:
        if verbose and not quiet:
            click.echo("Parsing DSL file...")

        model = parse_dsl(dsl_content)

        if verbose and not quiet:
            click.echo(
                f"Found {len(model.pieces)} pieces and {len(model.connections)} connections"
            )

    except (DSLSyntaxError, DSLSemanticError, DSLValidationError) as e:
        if not quiet:
            click.echo(f"DSL Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        if not quiet:
            click.echo(f"Unexpected error parsing DSL: {e}", err=True)
        sys.exit(1)

    # Create assembly
    try:
        if verbose and not quiet:
            click.echo("Creating 3D assembly...")

        assembly = Assembly.of(model)

    except Exception as e:
        if not quiet:
            click.echo(f"Error creating assembly: {e}", err=True)
        sys.exit(1)

    # Try to display with build123d
    try:
        from nichiyou_daiku.shell import assembly_to_build123d

        if verbose and not quiet:
            click.echo("Converting to build123d model...")

        compound = assembly_to_build123d(assembly, fillet_radius=fillet_radius)

        # Try different viewers
        viewer_found = False

        # Try ocp_vscode first
        try:
            from ocp_vscode import show

            if not quiet:
                click.echo("Displaying in VS Code OCP CAD Viewer...")
            show(compound)
            viewer_found = True
        except ImportError:
            pass

        # Try jupyter_cadquery if available
        if not viewer_found:
            try:
                from jupyter_cadquery import show as jcq_show

                if not quiet:
                    click.echo("Displaying in Jupyter CadQuery...")
                jcq_show(compound)
                viewer_found = True
            except ImportError:
                pass

        if not viewer_found:
            if not quiet:
                click.echo(
                    "No 3D viewer found. Install ocp-vscode or jupyter-cadquery.",
                    err=True,
                )
                click.echo("\nTo install ocp-vscode:", err=True)
                click.echo("  uv add ocp-vscode", err=True)
            sys.exit(1)

    except ImportError:
        if not quiet:
            click.echo("build123d is required for 3D visualization.", err=True)
            click.echo("\nTo install visualization dependencies:", err=True)
            click.echo("  uv sync --all-extras", err=True)
        sys.exit(1)
    except Exception as e:
        if not quiet:
            click.echo(f"Error displaying model: {e}", err=True)
        sys.exit(1)
