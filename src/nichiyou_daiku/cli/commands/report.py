"""Report command for generating markdown reports from DSL files."""

import sys
from typing import Optional

import click

from nichiyou_daiku.cli.utils import read_dsl_file, validate_output_path
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

    # Extract resources
    try:
        if verbose and not quiet:
            click.echo("Extracting resources...")

        resources = extract_resources(model)

    except Exception as e:
        if not quiet:
            click.echo(f"Error extracting resources: {e}", err=True)
        sys.exit(1)

    # Generate report
    try:
        if verbose and not quiet:
            click.echo("Generating report...")

        report_content = generate_markdown_report(
            resources,
            project_name=project_name,
            include_cut_diagram=include_cut_diagram,
        )

    except Exception as e:
        if not quiet:
            click.echo(f"Error generating report: {e}", err=True)
        sys.exit(1)

    # Output report
    try:
        output_path = validate_output_path(output)

        if output_path:
            output_path.write_text(report_content, encoding="utf-8")
            if not quiet:
                click.echo(f"Report written to: {output_path}")
        else:
            # Output to stdout
            click.echo(report_content)

    except click.ClickException as e:
        if not quiet:
            click.echo(f"Output error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        if not quiet:
            click.echo(f"Unexpected error writing output: {e}", err=True)
        sys.exit(1)
