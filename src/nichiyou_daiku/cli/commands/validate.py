"""Validate command for DSL files."""

import sys

import click

from nichiyou_daiku.cli.utils import read_dsl_file, CliEcho
from nichiyou_daiku.core.assembly import Assembly, find_joints_outside_pieces
from nichiyou_daiku.core.model import Model
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


def _unconnected_groups(model: Model) -> list[list[str]]:
    """Group piece IDs by connectivity; more than one group means floating pieces."""
    neighbours: dict[str, set[str]] = {piece_id: set() for piece_id in model.pieces}
    for base_id, target_id in model.connections:
        neighbours[base_id].add(target_id)
        neighbours[target_id].add(base_id)

    groups: list[list[str]] = []
    seen: set[str] = set()
    for start in model.pieces:
        if start in seen:
            continue
        group, stack = [], [start]
        seen.add(start)
        while stack:
            piece_id = stack.pop()
            group.append(piece_id)
            for neighbour in neighbours[piece_id] - seen:
                seen.add(neighbour)
                stack.append(neighbour)
        groups.append(sorted(group))
    return groups


def _geometry_problems(assembly: Assembly, groups: list[list[str]]) -> list[str]:
    """Overlaps and contradicting joints found by building the 3D model.

    Unconnected groups have no relative position (each sits at the origin),
    so overlaps are only checked within a group.
    """
    from nichiyou_daiku.shell.build123d_export import (
        assembly_to_build123d,
        check_overlap,
        find_joint_mismatches,
    )

    compound = assembly_to_build123d(assembly, fillet_radius=0)
    problems = []
    group_of = {piece_id: i for i, group in enumerate(groups) for piece_id in group}
    overlap = check_overlap(compound)
    for lhs, rhs in overlap.overlapping_pairs:
        if group_of.get(lhs) == group_of.get(rhs):
            problems.append(f"Pieces '{lhs}' and '{rhs}' overlap")
    for lhs_joint, rhs_joint, distance in find_joint_mismatches(assembly, compound):
        problems.append(
            f"Joints {lhs_joint} and {rhs_joint} are {distance:.1f}mm apart: "
            "this connection contradicts the others"
        )
    return problems


@click.command()
@click.argument("file", type=str)
@click.option(
    "--no-geometry",
    is_flag=True,
    help="Skip the 3D checks for overlapping pieces and contradicting joints.",
)
@click.pass_context
def validate(ctx: click.Context, file: str, no_geometry: bool) -> None:
    """Validate a DSL file and the model it describes.

    Checks the syntax, then builds the assembly and, when build123d is
    installed, the 3D model to find overlapping pieces, connections that
    contradict each other, and dowels that fall outside their piece.

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

    groups = _unconnected_groups(model)
    if len(groups) > 1:
        listed = "; ".join(", ".join(group) for group in groups)
        problems.append(
            "Some pieces are not connected to each other, so their relative "
            f"position is undefined (groups: {listed})"
        )

    from nichiyou_daiku.shell.build123d_export import HAS_BUILD123D

    if no_geometry:
        echo.verbose("Skipping 3D geometry checks (--no-geometry)")
    elif not HAS_BUILD123D:
        echo.info("3D geometry checks skipped: build123d is not installed")
    else:
        try:
            problems.extend(_geometry_problems(assembly, groups))
        except Exception as e:
            report_validation_error(echo, "Error building 3D model", e)
            sys.exit(1)

    if problems:
        echo.error(click.style("✗ Model has problems", fg="red", bold=True))
        for problem in problems:
            echo.error(f"  - {problem}")
        sys.exit(1)

    echo.echo(click.style("✓ Model is valid", fg="green"))
