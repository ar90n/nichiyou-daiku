"""Validate command for DSL files."""

import sys

import click

from nichiyou_daiku.cli.utils import read_dsl_file, CliEcho
from nichiyou_daiku.dsl import (
    parse_dsl,
    DSLSyntaxError,
    DSLSemanticError,
    DSLValidationError,
)


def report_validation_error(
    echo: CliEcho, error_type: str, exception: Exception
) -> None:
    """Report validation error with consistent formatting.

    Args:
        echo: CliEcho instance
        error_type: Type of error (e.g., "Syntax error", "Semantic error")
        exception: The exception to report
    """
    echo.error(click.style(f"✗ {error_type}", fg="red", bold=True))
    echo.error(f"\n{exception}")


@click.command()
@click.argument("file", type=str)
@click.pass_context
def validate(ctx: click.Context, file: str) -> None:
    """Validate DSL syntax and structure.

    FILE: Path to .nd file or '-' for stdin
    """
    echo = CliEcho(ctx)

    # Read DSL content
    try:
        dsl_content = read_dsl_file(file)
    except click.ClickException as e:
        echo.error(f"Error: {e}")
        sys.exit(1)

    # Validate DSL
    try:
        model = parse_dsl(dsl_content)

        echo.echo(click.style("✓ DSL syntax is valid", fg="green"))

        if echo._verbose:
            echo.echo("\nModel summary:")
            echo.echo(f"  Pieces: {len(model.pieces)}")
            echo.echo(f"  Connections: {len(model.connections)}")

            if model.pieces:
                echo.echo("\nPieces:")
                for piece_id, piece in model.pieces.items():
                    echo.echo(f"  - {piece_id}: {piece.type.value} @ {piece.length}mm")

        sys.exit(0)

    except DSLSyntaxError as e:
        report_validation_error(echo, "Syntax error", e)
        sys.exit(1)

    except DSLSemanticError as e:
        report_validation_error(echo, "Semantic error", e)
        sys.exit(1)

    except DSLValidationError as e:
        report_validation_error(echo, "Validation error", e)
        sys.exit(1)

    except Exception as e:
        report_validation_error(echo, "Unexpected error", e)
        sys.exit(1)
