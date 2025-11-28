"""Common utilities for CLI commands."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import click

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


def setup_logging(debug: bool, verbose: bool, quiet: bool) -> None:
    """Configure logging based on CLI flags.

    Args:
        debug: Enable debug logging
        verbose: Enable verbose logging
        quiet: Minimize output
    """
    import logging

    if quiet:
        level = logging.ERROR
    elif debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


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


def _echo_with_flags(
    message: str,
    *,
    err: bool = False,
    verbose_only: bool = False,
    quiet: bool = False,
    verbose: bool = False,
    **kwargs,
) -> None:
    """Smart echo that respects quiet/verbose flags.

    Args:
        message: Message to display
        err: Whether this is an error message (shown even in quiet mode)
        verbose_only: Only show this message in verbose mode
        quiet: Current quiet flag state
        verbose: Current verbose flag state
        **kwargs: Additional arguments passed to click.echo
    """
    if quiet and not err:  # Always show errors even in quiet mode
        return
    if verbose_only and not verbose:
        return
    click.echo(message, err=err, **kwargs)


class CliEcho:
    """Context-aware echo wrapper for CLI commands."""

    def __init__(self, ctx: click.Context):
        """Initialize with CLI context.

        Args:
            ctx: Click context containing quiet/verbose flags
        """
        self._quiet = ctx.obj.get("quiet", False)
        self._verbose = ctx.obj.get("verbose", False)

    def echo(
        self, message: str, *, err: bool = False, verbose_only: bool = False, **kwargs
    ) -> None:
        """Echo with automatic quiet/verbose handling.

        Args:
            message: Message to display
            err: Whether this is an error message
            verbose_only: Only show in verbose mode
            **kwargs: Additional arguments for click.echo
        """
        _echo_with_flags(
            message,
            err=err,
            verbose_only=verbose_only,
            quiet=self._quiet,
            verbose=self._verbose,
            **kwargs,
        )

    def error(self, message: str, **kwargs) -> None:
        """Echo error message (shown even in quiet mode).

        Args:
            message: Error message to display
            **kwargs: Additional arguments for click.echo
        """
        click.echo(message, err=True, **kwargs)

    def verbose(self, message: str, **kwargs) -> None:
        """Echo verbose message (only shown with --verbose).

        Args:
            message: Verbose message to display
            **kwargs: Additional arguments for click.echo
        """
        self.echo(message, verbose_only=True, **kwargs)


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
        echo.error(f"Unexpected error parsing DSL: {e}")
        sys.exit(1)


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
        return Assembly.of(model)
    except Exception as e:
        echo.error(f"Error creating assembly: {e}")
        sys.exit(1)


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
        echo.error(f"Error converting to 3D model: {e}")
        sys.exit(1)
