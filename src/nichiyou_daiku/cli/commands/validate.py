"""Validate command for DSL files."""

import sys

import click

from nichiyou_daiku.cli.utils import read_dsl_file
from nichiyou_daiku.dsl import (
    parse_dsl,
    DSLSyntaxError,
    DSLSemanticError,
    DSLValidationError,
)


@click.command()
@click.argument("file", type=str)
@click.pass_context
def validate(ctx: click.Context, file: str) -> None:
    """Validate DSL syntax and structure.

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

    # Validate DSL
    try:
        model = parse_dsl(dsl_content)

        if not quiet:
            click.echo(click.style("✓ DSL syntax is valid", fg="green"))

        if verbose:
            click.echo("\nModel summary:")
            click.echo(f"  Pieces: {len(model.pieces)}")
            click.echo(f"  Connections: {len(model.connections)}")

            if model.pieces:
                click.echo("\nPieces:")
                for piece_id, piece in model.pieces.items():
                    click.echo(f"  - {piece_id}: {piece.type.value} @ {piece.length}mm")

        sys.exit(0)

    except DSLSyntaxError as e:
        if not quiet:
            click.echo(click.style("✗ Syntax error", fg="red", bold=True), err=True)
            click.echo(f"\n{e}", err=True)
        sys.exit(1)

    except DSLSemanticError as e:
        if not quiet:
            click.echo(click.style("✗ Semantic error", fg="red", bold=True), err=True)
            click.echo(f"\n{e}", err=True)
        sys.exit(1)

    except DSLValidationError as e:
        if not quiet:
            click.echo(click.style("✗ Validation error", fg="red", bold=True), err=True)
            click.echo(f"\n{e}", err=True)
        sys.exit(1)

    except Exception as e:
        if not quiet:
            click.echo(click.style("✗ Unexpected error", fg="red", bold=True), err=True)
            click.echo(f"\n{e}", err=True)
        sys.exit(1)
