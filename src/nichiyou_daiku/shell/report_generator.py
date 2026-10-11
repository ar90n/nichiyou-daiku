"""Report generation from resource summaries.

This module converts ResourceSummary data into human-readable formats
following the functional core, imperative shell pattern.
"""

from typing import Dict, List, Optional
from datetime import datetime

from nichiyou_daiku.core.piece import PieceType
from .cutting import DEFAULT_STANDARD_LENGTHS, _optimize_cuts, _oversize_pieces
from .resources import ResourceSummary, PieceResource, format_mm


def _oversize_warning(
    pieces: List[PieceResource], available_lengths: List[float]
) -> List[str]:
    longest = max(available_lengths)
    return [
        f"- ⚠ {p.id} ({format_mm(p.length)}mm) is longer than the longest available "
        f"board ({longest:.0f}mm) and cannot be cut from stock"
        for p in _oversize_pieces(pieces, available_lengths)
    ]


def _generate_overview_section(summary: ResourceSummary, project_name: str) -> str:
    """Generate project overview section.

    Args:
        summary: Resource summary data
        project_name: Name of the project

    Returns:
        Markdown formatted overview section
    """
    # Calculate estimated weight (assuming pine density ~0.5 g/cm³)
    volume_cm3 = summary.total_volume / 1000  # mm³ to cm³
    estimated_weight_kg = volume_cm3 * 0.5 / 1000  # g to kg

    lumber_types = ", ".join(sorted(pt.value for pt in summary.pieces_by_type.keys()))

    size_line = ""
    if summary.overall_size is not None:
        x, y, z = summary.overall_size
        size_line = (
            f"- **Overall Size (X × Y × Z)**: {format_mm(x)} × {format_mm(y)} × {format_mm(z)} mm "
            f"(Z is the length direction of '{summary.size_reference}')\n"
        )

    return f"""# {project_name} Report

*Generated on {datetime.now().strftime("%Y-%m-%d %H:%M")}*

## Project Overview

{size_line}- **Total Pieces**: {summary.total_pieces}
- **Lumber Types**: {len(summary.pieces_by_type)} ({lumber_types})
- **Total Volume**: {summary.total_volume:,.0f} mm³
- **Estimated Weight**: ~{estimated_weight_kg:.1f} kg (assuming pine density)

"""


def _generate_warnings_section(summary: ResourceSummary) -> str:
    """List the design's problems near the top so they are not missed when
    building from the report alone."""
    lines = [
        "## Warnings",
        "",
        "The design has problems. Fix them before building:",
        "",
        *(f"- {issue}" for issue in summary.issues),
        "",
    ]
    return "\n".join(lines)


def _generate_bill_of_materials(summary: ResourceSummary) -> str:
    """Generate detailed bill of materials table.

    Args:
        summary: Resource summary data

    Returns:
        Markdown formatted BOM table
    """
    lines = [
        "## Bill of Materials",
        "",
        "| ID | Type | Length (mm) | Width (mm) | Height (mm) | Volume (mm³) |",
        "|----|------|------------|-----------|------------|-------------|",
    ]

    # Sort pieces by type then by length
    sorted_pieces = sorted(summary.pieces, key=lambda p: (p.type.value, p.length))

    for piece in sorted_pieces:
        lines.append(
            f"| {piece.id} | {piece.type.value} | {format_mm(piece.length)} | "
            f"{piece.width:.0f} | {piece.height:.0f} | {piece.volume:,.0f} |"
        )

    lines.extend(["", ""])
    return "\n".join(lines)


def _generate_shopping_list(summary: ResourceSummary) -> str:
    """Generate aggregated shopping list.

    Args:
        summary: Resource summary data

    Returns:
        Markdown formatted shopping list
    """
    lines = ["## Shopping List", "", "### Lumber Required:", ""]

    for piece_type in sorted(summary.pieces_by_type.keys(), key=lambda x: x.value):
        count = summary.pieces_by_type[piece_type]
        total_length = summary.total_length_by_type[piece_type]
        length_m = total_length / 1000

        lines.append(
            f"- **{piece_type.value}**: {count} pieces, total {length_m:.1f} meters"
        )

    lines.extend(["", ""])
    return "\n".join(lines)


def _generate_purchase_recommendations(
    summary: ResourceSummary,
    standard_lengths: Dict[PieceType, List[float]],
) -> str:
    """Generate purchase recommendations with cut optimization.

    Args:
        summary: Resource summary data
        standard_lengths: Available standard lengths per piece type

    Returns:
        Markdown formatted purchase recommendations
    """
    lines = ["## Purchase Recommendations", ""]

    for piece_type in sorted(summary.pieces_by_type.keys(), key=lambda x: x.value):
        pieces = [p for p in summary.pieces if p.type == piece_type]
        available_lengths = standard_lengths.get(
            piece_type, [2440.0]
        )  # Default fallback

        cut_plans = _optimize_cuts(pieces, available_lengths)

        # Calculate board requirements
        board_counts: Dict[float, int] = {}
        total_waste = 0.0
        total_purchased_length = 0.0

        for plan in cut_plans:
            board_counts[plan.board_length] = board_counts.get(plan.board_length, 0) + 1
            total_waste += plan.waste
            total_purchased_length += plan.board_length

        waste_percentage = (
            (total_waste / total_purchased_length) * 100
            if total_purchased_length > 0
            else 0
        )

        # Format available lengths
        lengths_str = ", ".join(
            f"{length:.0f}mm" for length in sorted(available_lengths)
        )

        lines.extend(
            [
                f"### {piece_type.value} Lumber (Available: {lengths_str})",
                "Optimal purchase:",
            ]
        )

        for board_length in sorted(board_counts.keys()):
            count = board_counts[board_length]
            lines.append(f"- {count} × {board_length:.0f}mm boards")

        lines.append(
            f"Total waste: {format_mm(total_waste)}mm ({waste_percentage:.1f}%)"
        )
        lines.extend(_oversize_warning(pieces, available_lengths))
        lines.append("")

    return "\n".join(lines)


def _generate_cut_list(
    summary: ResourceSummary,
    standard_lengths: Dict[PieceType, List[float]],
) -> str:
    """Generate optimized cut list with ASCII diagrams.

    Args:
        summary: Resource summary data
        standard_lengths: Available standard lengths per piece type

    Returns:
        Markdown formatted cut list
    """
    lines = ["## Optimized Cut List", ""]

    for piece_type in sorted(summary.pieces_by_type.keys(), key=lambda x: x.value):
        pieces = [p for p in summary.pieces if p.type == piece_type]
        available_lengths = standard_lengths.get(piece_type, [2440.0])

        cut_plans = _optimize_cuts(pieces, available_lengths)

        lines.extend([f"### {piece_type.value} Boards", ""])
        warnings = _oversize_warning(pieces, available_lengths)
        if warnings:
            lines.extend([*warnings, ""])

        for i, plan in enumerate(cut_plans, 1):
            lines.append(f"**Board {i}** ({plan.board_length:.0f}mm):")

            # Create simple cut list
            for piece_id, length in plan.cuts:
                lines.append(f"- Cut {format_mm(length)}mm → {piece_id}")

            if plan.waste > 0:
                lines.append(f"- Waste: {format_mm(plan.waste)}mm")

            lines.append("")

    return "\n".join(lines)


def _generate_anchor_details(summary: ResourceSummary) -> str:
    """Generate anchor position details for each piece.

    Args:
        summary: Resource summary data

    Returns:
        Markdown formatted anchor details section
    """
    lines = [
        "## Anchor Details",
        "",
    ]

    # Filter pieces that have anchors and sort by ID
    pieces_with_anchors = [p for p in summary.pieces if p.anchors]
    pieces_with_anchors.sort(key=lambda p: p.id)

    if not pieces_with_anchors:
        # No pieces with anchors, return empty section indicator
        lines.append("*No anchor points in this project.*")
        lines.append("")
        return "\n".join(lines)

    for piece in pieces_with_anchors:
        # Piece header with type and length
        lines.extend(
            [f"### {piece.id} ({piece.type.value}, {format_mm(piece.length)}mm)", ""]
        )

        # Table header
        lines.extend(
            [
                "| Contact Face | Edge Face | Offset |",
                "|--------------|-----------|--------|",
            ]
        )

        # Table rows
        for anchor in piece.anchors:
            lines.append(
                f"| {anchor.contact_face} | {anchor.edge_shared_face} | "
                f"{anchor.offset_type} {anchor.offset_value:.1f}mm |"
            )

        lines.append("")

    return "\n".join(lines)


def _generate_face_diagram(
    holes: list, face: str, width: float, height: float
) -> list[str]:
    """Generate ASCII diagram for a single face.

    Args:
        holes: List of PilotHoleInfo for this face
        face: Face name (top, down, left, right, front, back)
        width: Width of the diagram area in mm
        height: Height of the diagram area in mm

    Returns:
        List of lines for the ASCII diagram
    """
    # Diagram dimensions (characters)
    DIAGRAM_WIDTH = 40
    DIAGRAM_HEIGHT = 5

    lines = []
    lines.append("```")
    lines.append(f"{face} ({width:.0f}mm x {height:.0f}mm):")

    # Create empty grid
    grid = [[" " for _ in range(DIAGRAM_WIDTH + 2)] for _ in range(DIAGRAM_HEIGHT + 2)]

    # Draw border
    for x in range(DIAGRAM_WIDTH + 2):
        grid[0][x] = "-"
        grid[DIAGRAM_HEIGHT + 1][x] = "-"
    for y in range(DIAGRAM_HEIGHT + 2):
        grid[y][0] = "|"
        grid[y][DIAGRAM_WIDTH + 1] = "|"
    grid[0][0] = "+"
    grid[0][DIAGRAM_WIDTH + 1] = "+"
    grid[DIAGRAM_HEIGHT + 1][0] = "+"
    grid[DIAGRAM_HEIGHT + 1][DIAGRAM_WIDTH + 1] = "+"

    # Place holes
    for hole in holes:
        # Scale coordinates to grid
        x = int((hole.from_length_edge / width) * DIAGRAM_WIDTH) + 1
        y = int((hole.from_width_edge / height) * DIAGRAM_HEIGHT) + 1

        # Clamp to valid range
        x = max(1, min(DIAGRAM_WIDTH, x))
        y = max(1, min(DIAGRAM_HEIGHT, y))

        grid[y][x] = "o"

    # Convert grid to lines
    for row in grid:
        lines.append("".join(row))

    lines.append("```")
    return lines


def _generate_pilot_holes_section(summary: ResourceSummary) -> str:
    """Generate pilot hole drilling guide for each piece.

    Args:
        summary: Resource summary data

    Returns:
        Markdown formatted pilot holes section with tables and ASCII diagrams
    """
    lines = [
        "## Pilot Holes",
        "",
    ]

    # Filter pieces that have pilot holes and sort by ID
    pieces_with_holes = [p for p in summary.pieces if p.pilot_holes]
    pieces_with_holes.sort(key=lambda p: p.id)

    if not pieces_with_holes:
        lines.append("*No pilot holes in this project.*")
        lines.append("")
        return "\n".join(lines)

    lines.extend(
        [
            "Distances are measured on the face the hole is drilled into:",
            "- front/back faces: *From Length Edge* from the down end, "
            "*From Width Edge* from the left side",
            "- left/right faces: *From Length Edge* from the down end, "
            "*From Width Edge* from the back side",
            "- top/down (end) faces: *From Length Edge* from the left side, "
            "*From Width Edge* from the back side",
            "",
        ]
    )

    for piece in pieces_with_holes:
        # Piece header
        lines.extend(
            [f"### {piece.id} ({piece.type.value}, {format_mm(piece.length)}mm)", ""]
        )

        # Table header
        lines.extend(
            [
                "| Face | From Length Edge | From Width Edge | Diameter | Depth |",
                "|---|---|---|---|---|",
            ]
        )

        # Group holes by face for diagram generation
        holes_by_face: dict[str, list] = {}

        # Table rows
        for hole in piece.pilot_holes:
            depth_str = f"{hole.depth:.1f}mm" if hole.depth is not None else "through"
            lines.append(
                f"| {hole.face} | {hole.from_length_edge:.1f}mm | "
                f"{hole.from_width_edge:.1f}mm | φ{hole.diameter:.1f}mm | {depth_str} |"
            )

            # Group for diagram
            if hole.face not in holes_by_face:
                holes_by_face[hole.face] = []
            holes_by_face[hole.face].append(hole)

        lines.append("")

        # Generate ASCII diagrams for each face with holes
        for face, face_holes in sorted(holes_by_face.items()):
            # Determine diagram dimensions based on face
            if face in ("top", "down"):
                diagram_width = piece.width
                diagram_height = piece.height
            elif face in ("left", "right"):
                diagram_width = piece.length
                diagram_height = piece.height
            else:  # front, back
                diagram_width = piece.length
                diagram_height = piece.width

            diagram_lines = _generate_face_diagram(
                face_holes, face, diagram_width, diagram_height
            )
            lines.extend(diagram_lines)
            lines.append("")

    return "\n".join(lines)


def generate_markdown_report(
    resource_summary: ResourceSummary,
    project_name: str = "Woodworking Project",
    standard_lengths: Optional[Dict[PieceType, List[float]]] = None,
    include_cut_diagram: bool = True,
    include_anchor_details: bool = True,
    include_pilot_holes: bool = True,
) -> str:
    """Generate a complete markdown report from ResourceSummary.

    Args:
        resource_summary: The resource summary to report on
        project_name: Name of the project
        standard_lengths: Dict mapping PieceType to available lengths in mm.
                        If None, uses sensible defaults.
        include_cut_diagram: Whether to include cut list section
        include_anchor_details: Whether to include anchor details section
        include_pilot_holes: Whether to include pilot holes section

    Returns:
        Complete markdown report as string

    Examples:
        >>> from nichiyou_daiku.core.piece import PieceType
        >>> from nichiyou_daiku.shell.resources import ResourceSummary, PieceResource
        >>> pieces = [
        ...     PieceResource(id="test", type=PieceType.PT_2x4, length=1000.0,
        ...                  width=89.0, height=38.0, volume=3382000.0)
        ... ]
        >>> summary = ResourceSummary(
        ...     pieces=pieces, total_pieces=1,
        ...     pieces_by_type={PieceType.PT_2x4: 1},
        ...     total_length_by_type={PieceType.PT_2x4: 1000.0},
        ...     total_volume=3382000.0
        ... )
        >>> report = generate_markdown_report(summary, "Test Project")
        >>> "# Test Project Report" in report
        True
        >>> "## Bill of Materials" in report
        True
        >>> "PT_2x4" not in report  # Should show "2x4", not enum name
        True
    """
    if standard_lengths is None:
        standard_lengths = DEFAULT_STANDARD_LENGTHS

    # Generate all sections
    sections = []

    sections.append(_generate_overview_section(resource_summary, project_name))
    if resource_summary.issues:
        sections.append(_generate_warnings_section(resource_summary))
    sections.append(_generate_bill_of_materials(resource_summary))

    # Add anchor details after BOM, before pilot holes
    if include_anchor_details:
        sections.append(_generate_anchor_details(resource_summary))

    # Add pilot holes section after anchor details
    if include_pilot_holes:
        sections.append(_generate_pilot_holes_section(resource_summary))

    sections.append(_generate_shopping_list(resource_summary))
    sections.append(
        _generate_purchase_recommendations(resource_summary, standard_lengths)
    )

    if include_cut_diagram:
        sections.append(_generate_cut_list(resource_summary, standard_lengths))

    # Add footer
    sections.append("---\n*Report generated by nichiyou-daiku*")

    return "\n".join(sections)
