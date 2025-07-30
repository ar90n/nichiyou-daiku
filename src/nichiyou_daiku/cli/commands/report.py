"""Report command for generating markdown reports from DSL files."""

import sys
from typing import Optional

import click

from nichiyou_daiku.cli.utils import read_dsl_file, validate_output_path, CliEcho
from nichiyou_daiku.dsl import (
    parse_dsl,
    DSLSyntaxError,
    DSLSemanticError,
    DSLValidationError,
)
from nichiyou_daiku.core.resources import extract_resources
from nichiyou_daiku.shell import generate_markdown_report


@click.command()
@click.argument("file", type=str)
@click.option("-o", "--output", type=str, help="Output file path (default: stdout)")
@click.option(
    "--project-name",
    type=str,
    default="Woodworking Project",
    help="Project name for report",
)
@click.option(
    "--include-cut-diagram/--no-cut-diagram",
    default=True,
    help="Include cut diagram in report",
)
@click.pass_context
def report(
    ctx: click.Context,
    file: str,
    output: Optional[str],
    project_name: str,
    include_cut_diagram: bool,
) -> None:
    """Generate a markdown report from DSL file.

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

    # Extract resources
    try:
        echo.verbose("Extracting resources...")

        resources = extract_resources(model)

    except Exception as e:
        echo.error(f"Error extracting resources: {e}")
        sys.exit(1)

    # Generate report
    try:
        echo.verbose("Generating report...")

        report_content = generate_markdown_report(
            resources,
            project_name=project_name,
            include_cut_diagram=include_cut_diagram,
        )

    except Exception as e:
        echo.error(f"Error generating report: {e}")
        sys.exit(1)

    # Output report
    try:
        output_path = validate_output_path(output)

        if output_path:
            output_path.write_text(report_content, encoding="utf-8")
            echo.echo(f"Report written to: {output_path}")
        else:
            # Output to stdout
            click.echo(report_content)

    except click.ClickException as e:
        echo.error(f"Output error: {e}")
        sys.exit(1)
    except Exception as e:
        echo.error(f"Unexpected error writing output: {e}")
        sys.exit(1)
