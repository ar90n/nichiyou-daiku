"""Main CLI entry point for nichiyou-daiku DSL tools."""

import click

from nichiyou_daiku.cli.commands.validate import validate
from nichiyou_daiku.cli.commands.report import report
from nichiyou_daiku.cli.commands.view import view
from nichiyou_daiku.cli.commands.export import export
from nichiyou_daiku.cli.commands.drawing import drawing
from nichiyou_daiku.cli.commands.render import render
from nichiyou_daiku.cli.commands.steps import steps


@click.group()
@click.option(
    "--debug", "-d", is_flag=True, help="Show tracebacks for unexpected errors"
)
@click.option("--verbose", "-v", is_flag=True, help="Show progress messages")
@click.option("--quiet", "-q", is_flag=True, help="Minimize output")
@click.pass_context
def cli(ctx: click.Context, debug: bool, verbose: bool, quiet: bool) -> None:
    """nichiyou-daiku DSL command line tools.

    Process .nd files to generate 3D models, reports, and more.
    """
    # Ensure that ctx.obj exists and is a dict
    ctx.ensure_object(dict)

    # Store options in context for subcommands
    ctx.obj["debug"] = debug
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet


cli.add_command(validate)
cli.add_command(report)
cli.add_command(view)
cli.add_command(export)
cli.add_command(drawing)
cli.add_command(render)
cli.add_command(steps)


if __name__ == "__main__":
    cli()
