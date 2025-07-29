"""Common utilities for CLI commands."""

import sys
from pathlib import Path
from typing import Optional

import click


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
