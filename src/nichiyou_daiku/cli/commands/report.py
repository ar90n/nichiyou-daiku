"""Report command for generating markdown reports from DSL files."""

import sys
from typing import Optional

import click

from nichiyou_daiku.cli.utils import (
    CliEcho,
    create_assembly_from_model,
    parse_dsl_to_model,
    read_dsl_file,
    validate_output_path,
)
from nichiyou_daiku.shell import extract_resources, generate_markdown_report


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
@click.option(
    "--include-anchor-details/--no-anchor-details",
    default=True,
    help="Include anchor details in report",
)
@click.option(
    "--include-pilot-holes/--no-pilot-holes",
    default=True,
    help="Include pilot holes drilling guide in report",
)
@click.pass_context
def report(
    ctx: click.Context,
    file: str,
    output: Optional[str],
    project_name: str,
    include_cut_diagram: bool,
    include_anchor_details: bool,
    include_pilot_holes: bool,
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

    # Parse DSL and create assembly
    model = parse_dsl_to_model(dsl_content, echo)
    assembly = create_assembly_from_model(model, echo)

    # Extract resources
    try:
        echo.verbose("Extracting resources...")

        resources = extract_resources(assembly)

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
            include_anchor_details=include_anchor_details,
            include_pilot_holes=include_pilot_holes,
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
