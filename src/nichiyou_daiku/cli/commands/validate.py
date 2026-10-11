"""Validate command for DSL files."""

import sys

import click

from nichiyou_daiku.cli.utils import (
    CliEcho,
    describe_placement_issues,
    format_mm,
    read_dsl_file,
)
from nichiyou_daiku.core.assembly import Assembly, find_joints_outside_pieces
from nichiyou_daiku.core.placement import find_overlaps
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
    echo.exception(f"\n{exception}")


@click.command()
@click.argument("file", type=str)
@click.pass_context
def validate(ctx: click.Context, file: str) -> None:
    """Validate a DSL file and the model it describes.

    Checks the syntax, builds the assembly and solves the placement, then
    reports contradicting connections, unconnected pieces, overlapping
    pieces and dowels that fall outside their piece.

    FILE: Path to .nd file or '-' for stdin
    """
    echo = CliEcho(ctx)

    # Read DSL content
    try:
        dsl_content = read_dsl_file(file)
    except click.ClickException as e:
        echo.error(f"Error: {e}")
        sys.exit(1)

    try:
        model = parse_dsl(dsl_content)
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

    echo.echo(click.style("✓ DSL syntax is valid", fg="green"))
    echo.echo("\nModel summary:", verbose_only=True)
    echo.echo(f"  Pieces: {len(model.pieces)}", verbose_only=True)
    echo.echo(f"  Connections: {len(model.connections)}", verbose_only=True)
    if model.pieces:
        echo.echo("\nPieces:", verbose_only=True)
        for piece_id, piece in model.pieces.items():
            echo.echo(
                f"  - {piece_id}: {piece.type.value} @ {piece.length}mm",
                verbose_only=True,
            )

    try:
        assembly = Assembly.of(model)
    except Exception as e:
        report_validation_error(echo, "Assembly error", e)
        sys.exit(1)

    problems = [
        f"Joint {joint_id} lies outside piece "
        f"'{joint_id.rsplit('_j', 1)[0]}': the dowel layout does not fit this joint"
        for joint_id in find_joints_outside_pieces(assembly)
    ]
    problems += describe_placement_issues(assembly.placement)
    problems += [
        f"Pieces '{overlap.lhs}' and '{overlap.rhs}' overlap "
        f"({format_mm(overlap.volume)}mm³)"
        for overlap in find_overlaps(model, assembly.placement)
    ]

    if problems:
        echo.error(click.style("✗ Model has problems", fg="red", bold=True))
        for problem in problems:
            echo.error(f"  - {problem}")
        sys.exit(1)

    echo.echo(click.style("✓ Model is valid", fg="green"))
