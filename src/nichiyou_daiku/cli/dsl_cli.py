"""Main CLI entry point for nichiyou-daiku DSL tools."""

import click

from nichiyou_daiku.cli.utils import setup_logging
from nichiyou_daiku.cli.commands.validate import validate
from nichiyou_daiku.cli.commands.report import report
from nichiyou_daiku.cli.commands.view import view


@click.group()
@click.option("--debug", "-d", is_flag=True, help="Enable debug logging")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--quiet", "-q", is_flag=True, help="Minimize output")
@click.pass_context
def cli(ctx: click.Context, debug: bool, verbose: bool, quiet: bool) -> None:
    """nichiyou-daiku DSL command line tools.

    Process .nd files to generate 3D models, reports, and more.
    """
    # Ensure that ctx.obj exists and is a dict
    ctx.ensure_object(dict)

    # Setup logging
    setup_logging(debug, verbose, quiet)

    # Store options in context for subcommands
    ctx.obj["debug"] = debug
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet


cli.add_command(validate)
cli.add_command(report)
cli.add_command(view)


if __name__ == "__main__":
    cli()
