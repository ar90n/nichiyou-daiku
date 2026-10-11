"""Common utilities for CLI commands."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import click

from nichiyou_daiku.shell.report_generator import format_mm

if TYPE_CHECKING:
    from nichiyou_daiku.core.assembly import Assembly
    from nichiyou_daiku.core.model import Model


def read_dsl_file(file_path: str) -> str:
    """Read DSL content from a file or stdin.

    Args:
        file_path: Path to the .nd file or '-' for stdin

    Returns:
        DSL content as string

    Raises:
        click.ClickException: If file cannot be read
    """
    if file_path == "-":
        return sys.stdin.read()

    path = Path(file_path)
    if not path.exists():
        raise click.ClickException(f"File not found: {file_path}")

    if not path.is_file():
        raise click.ClickException(f"Not a file: {file_path}")

    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        raise click.ClickException(f"Error reading file: {e}")


def validate_output_path(output_path: Optional[str]) -> Optional[Path]:
    """Validate and prepare output path.

    Args:
        output_path: Output file path or None for stdout

    Returns:
        Path object or None for stdout

    Raises:
        click.ClickException: If output path is invalid
    """
    if output_path is None:
        return None

    path = Path(output_path)

    # Create parent directory if it doesn't exist
    if path.parent and not path.parent.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise click.ClickException(f"Cannot create output directory: {e}")

    # Check if we can write to the location
    if path.exists() and not path.is_file():
        raise click.ClickException(f"Output path is not a file: {output_path}")

    return path


def require_output_for_stdin(input_file: str, output: Optional[Path]) -> None:
    """Require -o when reading from stdin, since no output name can be derived.

    Raises:
        click.ClickException: If input is stdin and no output path was given
    """
    if input_file == "-" and output is None:
        raise click.ClickException(
            "An output file (-o) is required when reading from stdin ('-')."
        )


def ensure_not_overwriting_input(input_file: str, output_path: Path) -> None:
    """Refuse to write output over the input DSL file.

    Args:
        input_file: Input path as given on the command line ('-' for stdin)
        output_path: Path the command is about to write

    Raises:
        click.ClickException: If both paths refer to the same file
    """
    if input_file != "-" and Path(input_file).resolve() == output_path.resolve():
        raise click.ClickException(
            f"Refusing to overwrite the input file: {input_file}. "
            "Choose a different output path with -o."
        )


class CliEcho:
    """Context-aware echo wrapper for CLI commands."""

    def __init__(self, ctx: click.Context):
        """Initialize with CLI context.

        Args:
            ctx: Click context containing quiet/verbose flags
        """
        self._quiet = ctx.obj.get("quiet", False)
        self._verbose = ctx.obj.get("verbose", False)
        self._debug = ctx.obj.get("debug", False)

    def echo(self, message: str) -> None:
        """Echo command output to stdout (suppressed by --quiet)."""
        if not self._quiet:
            click.echo(message)

    def error(self, message: str, **kwargs) -> None:
        """Echo error message (shown even in quiet mode).

        Args:
            message: Error message to display
            **kwargs: Additional arguments for click.echo
        """
        click.echo(message, err=True, **kwargs)

    def exception(self, message: str) -> None:
        """Echo error message for the exception being handled.

        With --debug, the full traceback is printed to stderr as well.

        Args:
            message: Error message to display
        """
        self.error(message)
        if self._debug:
            click.echo(traceback.format_exc(), err=True, nl=False)

    def info(self, message: str, **kwargs) -> None:
        """Echo status message to stderr (suppressed by --quiet).

        Status goes to stderr so stdout carries only command output
        (e.g. `report x.nd > r.md` stays pure markdown).

        Args:
            message: Status message to display
            **kwargs: Additional arguments for click.echo
        """
        if not self._quiet:
            click.echo(message, err=True, **kwargs)

    def verbose(self, message: str, **kwargs) -> None:
        """Echo progress message to stderr (only shown with --verbose).

        Args:
            message: Verbose message to display
            **kwargs: Additional arguments for click.echo
        """
        if self._verbose:
            self.info(message, **kwargs)


def parse_dsl_to_model(dsl_content: str, echo: CliEcho) -> Model:
    """Parse DSL content to Model with error handling.

    Args:
        dsl_content: DSL content string
        echo: CliEcho instance for output

    Returns:
        Parsed Model object

    Raises:
        SystemExit: If parsing fails
    """
    from nichiyou_daiku.dsl import (
        DSLSemanticError,
        DSLSyntaxError,
        DSLValidationError,
        parse_dsl,
    )

    try:
        echo.verbose("Parsing DSL file...")
        model = parse_dsl(dsl_content)
        echo.verbose(
            f"Found {len(model.pieces)} pieces and {len(model.connections)} connections"
        )
        return model
    except (DSLSyntaxError, DSLSemanticError, DSLValidationError) as e:
        echo.error(f"DSL Error: {e}")
        sys.exit(1)
    except Exception as e:
        echo.exception(f"Unexpected error parsing DSL: {e}")
        sys.exit(1)


def describe_assembly_issues(assembly: Assembly) -> list[str]:
    """Human-readable lines for placement conflicts, unconnected pieces and
    fasteners that do not fit."""
    placement = assembly.placement
    issues = []
    for conflict in placement.conflicts:
        loop = " -> ".join(conflict.loop)
        where = f"Connection {conflict.base_id} -> {conflict.target_id}"
        if conflict.kind == "rotation":
            issues.append(
                f"{where}: orientation contradicts the other connections (loop: {loop})"
            )
        else:
            issues.append(
                f"{where}: {conflict.kind} ({conflict.axis}) is off by "
                f"{format_mm(abs(conflict.mismatch_mm or 0.0))}mm (loop: {loop})"
            )
    if len(placement.groups) > 1:
        listed = "; ".join(", ".join(group) for group in placement.groups)
        issues.append(
            "Some pieces are not connected to each other, so their relative "
            f"position is undefined (groups: {listed})"
        )
    issues += [
        f"Connection {issue.base_id} -> {issue.target_id}: {issue.message}"
        for issue in assembly.fastener_issues
    ]
    return issues


def warn_assembly_issues(assembly: Assembly, echo: CliEcho) -> None:
    """Warn on stderr about placement and fastener issues; the command carries on."""
    for issue in describe_assembly_issues(assembly):
        echo.info(click.style(f"Warning: {issue}", fg="yellow"))


def create_assembly_from_model(model: Model, echo: CliEcho) -> Assembly:
    """Create Assembly from Model with error handling.

    Args:
        model: Model object
        echo: CliEcho instance for output

    Returns:
        Assembly object

    Raises:
        SystemExit: If assembly creation fails
    """
    from nichiyou_daiku.core.assembly import Assembly

    try:
        echo.verbose("Creating assembly...")
        assembly = Assembly.of(model)
    except Exception as e:
        echo.exception(f"Error creating assembly: {e}")
        sys.exit(1)
    warn_assembly_issues(assembly, echo)
    return assembly


def ensure_build123d_available(echo: CliEcho) -> None:
    """Check if build123d is available, exit if not.

    Args:
        echo: CliEcho instance for output

    Raises:
        SystemExit: If build123d is not available
    """
    from nichiyou_daiku.shell.build123d_export import HAS_BUILD123D

    if not HAS_BUILD123D:
        echo.error(
            "Error: build123d is required for this operation.\n"
            "Please install it with: uv sync --all-extras"
        )
        sys.exit(1)


def convert_assembly_to_build123d(
    assembly: Assembly, echo: CliEcho, fillet_radius: float = 5.0
):
    """Convert Assembly to build123d Compound with error handling.

    Args:
        assembly: Assembly object
        echo: CliEcho instance for output
        fillet_radius: Fillet radius in mm (default: 5.0)

    Returns:
        build123d Compound object

    Raises:
        SystemExit: If conversion fails
    """
    from nichiyou_daiku.shell import assembly_to_build123d

    try:
        echo.verbose("Converting to build123d model...")
        return assembly_to_build123d(assembly, fillet_radius=fillet_radius)
    except Exception as e:
        echo.exception(f"Error converting to 3D model: {e}")
        sys.exit(1)
