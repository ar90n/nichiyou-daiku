"""Validate command for DSL files."""

import sys

import click

from nichiyou_daiku.cli.utils import CliEcho, read_dsl_file
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.dsl import (
    DSLSemanticError,
    DSLSyntaxError,
    DSLValidationError,
    parse_dsl,
)
from nichiyou_daiku.shell.diagnostics import (
    FailureKind,
    ValidationReport,
    collect_problems,
    failure_report,
    validation_report,
)

# The first class that matches names a parse error, in the text and the JSON
_PARSE_ERRORS: tuple[tuple[type[Exception], FailureKind, str], ...] = (
    (DSLSyntaxError, "syntax", "Syntax error"),
    (DSLSemanticError, "semantic", "Semantic error"),
    (DSLValidationError, "validation", "Validation error"),
    (Exception, "unexpected", "Unexpected error"),
)


def _classify(error: Exception) -> tuple[FailureKind, str]:
    return next(
        (kind, label)
        for error_class, kind, label in _PARSE_ERRORS
        if isinstance(error, error_class)
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


def _json_report(file: str) -> ValidationReport:
    try:
        content = read_dsl_file(file)
    except click.ClickException as e:
        return failure_report("file", e)
    try:
        model = parse_dsl(content)
    except Exception as e:
        return failure_report(_classify(e)[0], e)
    try:
        assembly = Assembly.of(model)
    except Exception as e:
        return failure_report("assembly", e)
    return validation_report(assembly)


@click.command()
@click.argument("file", type=str)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Print the result as one JSON object (problems, piece positions, "
    "overall size) for tools and agents.",
)
@click.pass_context
def validate(ctx: click.Context, file: str, as_json: bool) -> None:
    """Validate a DSL file and the model it describes.

    Checks the syntax, builds the assembly and solves the placement, then
    reports contradicting connections, unconnected pieces, overlapping
    pieces, fasteners that do not fit their joint and holes that collide.
    With --json, prints the same result with piece positions as JSON.

    FILE: Path to .nd file or '-' for stdin
    """
    if as_json:
        report = _json_report(file)
        # Not through CliEcho: the JSON is the output even with --quiet
        click.echo(report.model_dump_json(indent=2))
        sys.exit(0 if report.valid else 1)

    echo = CliEcho(ctx)

    try:
        dsl_content = read_dsl_file(file)
    except click.ClickException as e:
        echo.error(f"Error: {e}")
        sys.exit(1)

    try:
        model = parse_dsl(dsl_content)
    except Exception as e:
        report_validation_error(echo, _classify(e)[1], e)
        sys.exit(1)

    echo.echo(click.style("✓ DSL syntax is valid", fg="green"))
    echo.verbose("\nModel summary:")
    echo.verbose(f"  Pieces: {len(model.pieces)}")
    echo.verbose(f"  Connections: {len(model.connections)}")
    if model.pieces:
        echo.verbose("\nPieces:")
        for piece_id, piece in model.pieces.items():
            echo.verbose(f"  - {piece_id}: {piece.type.value} @ {piece.length}mm")

    try:
        assembly = Assembly.of(model)
    except Exception as e:
        report_validation_error(echo, "Assembly error", e)
        sys.exit(1)

    problems = [problem.message for problem in collect_problems(assembly)]
    if problems:
        echo.error(click.style("✗ Model has problems", fg="red", bold=True))
        for problem in problems:
            echo.error(f"  - {problem}")
        sys.exit(1)

    echo.echo(click.style("✓ Model is valid", fg="green"))
