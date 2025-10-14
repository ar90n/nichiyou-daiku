"""Report generation from resource summaries.

This module converts ResourceSummary data into human-readable formats
following the functional core, imperative shell pattern.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from nichiyou_daiku.core.piece import PieceType
from nichiyou_daiku.core.resources import ResourceSummary, PieceResource


@dataclass
class CutPlan:
    """Plan for cutting pieces from a standard board.

    Attributes:
        board_length: Length of the standard board in mm
        cuts: List of (piece_id, length) tuples to cut from this board
        waste: Remaining unused length in mm
    """

    board_length: float
    cuts: List[Tuple[str, float]]
    waste: float


def _get_default_standard_lengths() -> Dict[PieceType, List[float]]:
    """Get default standard lengths for each piece type.

    Returns:
        Dict mapping piece types to available standard lengths in mm

    Examples:
        >>> lengths = _get_default_standard_lengths()
        >>> PieceType.PT_2x4 in lengths
        True
        >>> len(lengths[PieceType.PT_2x4]) >= 3
        True
        >>> all(length > 2000 for length in lengths[PieceType.PT_2x4])
        True
    """
    return {
        PieceType.PT_2x4: [2440.0, 3050.0, 3660.0],  # 8ft, 10ft, 12ft
        PieceType.PT_1x4: [1830.0, 2440.0, 3050.0],  # 6ft, 8ft, 10ft
    }


def _optimize_cuts(
    pieces: List[PieceResource], available_lengths: List[float]
) -> List[CutPlan]:
    """Optimize piece cutting to minimize waste.

    Uses a simple first-fit decreasing algorithm to minimize waste.

    Args:
        pieces: List of pieces to cut (all same lumber type)
        available_lengths: Available standard board lengths in mm

    Returns:
        List of cut plans showing how to cut pieces from standard boards

    Examples:
        >>> from nichiyou_daiku.core.piece import PieceType
        >>> pieces = [
        ...     PieceResource(id="p1", type=PieceType.PT_2x4, length=1000.0,
        ...                  width=89.0, height=38.0, volume=0),
        ...     PieceResource(id="p2", type=PieceType.PT_2x4, length=800.0,
        ...                  width=89.0, height=38.0, volume=0)
        ... ]
        >>> plans = _optimize_cuts(pieces, [2440.0])
        >>> len(plans)
        1
        >>> plans[0].board_length
        2440.0
        >>> len(plans[0].cuts)
        2
        >>> plans[0].waste
        640.0
    """
    # Sort pieces by length (descending) for better optimization
    sorted_pieces = sorted(pieces, key=lambda p: p.length, reverse=True)

    # Sort available lengths (ascending) to prefer smaller boards when possible
    sorted_lengths = sorted(available_lengths)

    cut_plans = []
    remaining_pieces = sorted_pieces.copy()

    while remaining_pieces:
        # Find the best board length for remaining pieces
        best_plan = None
        best_waste = float("inf")
        best_remaining = remaining_pieces

        for board_length in sorted_lengths:
            cuts = []
            used_length = 0.0
            temp_remaining = remaining_pieces.copy()

            # Try to fit as many pieces as possible
            for piece in remaining_pieces:
                if used_length + piece.length <= board_length:
                    cuts.append((piece.id, piece.length))
                    used_length += piece.length
                    temp_remaining.remove(piece)

            if cuts:  # If we can fit at least one piece
                waste = board_length - used_length
                if waste < best_waste:
                    best_waste = waste
                    best_plan = CutPlan(
                        board_length=board_length, cuts=cuts, waste=waste
                    )
                    best_remaining = temp_remaining

        if best_plan:
            cut_plans.append(best_plan)
            remaining_pieces = best_remaining
        else:
            # If no standard length can fit the largest remaining piece
            # Use the largest available length
            largest_piece = remaining_pieces[0]
            largest_length = max(sorted_lengths)
            cut_plans.append(
                CutPlan(
                    board_length=largest_length,
                    cuts=[(largest_piece.id, largest_piece.length)],
                    waste=largest_length - largest_piece.length,
                )
            )
            remaining_pieces.remove(largest_piece)

    return cut_plans


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

    return f"""# {project_name} Report

*Generated on {datetime.now().strftime("%Y-%m-%d %H:%M")}*

## Project Overview

- **Total Pieces**: {summary.total_pieces}
- **Lumber Types**: {len(summary.pieces_by_type)} ({lumber_types})
- **Total Volume**: {summary.total_volume:,.0f} mm³
- **Estimated Weight**: ~{estimated_weight_kg:.1f} kg (assuming pine density)

"""


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
            f"| {piece.id} | {piece.type.value} | {piece.length:.0f} | "
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
    summary: ResourceSummary, standard_lengths: Dict[PieceType, List[float]]
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

        lines.extend(
            [f"Total waste: {total_waste:.0f}mm ({waste_percentage:.1f}%)", ""]
        )

    return "\n".join(lines)


def _generate_cut_list(
    summary: ResourceSummary, standard_lengths: Dict[PieceType, List[float]]
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

        for i, plan in enumerate(cut_plans, 1):
            lines.append(f"**Board {i}** ({plan.board_length:.0f}mm):")

            # Create simple cut list
            for piece_id, length in plan.cuts:
                lines.append(f"- Cut {length:.0f}mm → {piece_id}")

            if plan.waste > 0:
                lines.append(f"- Waste: {plan.waste:.0f}mm")

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
        lines.extend([f"### {piece.id} ({piece.type.value}, {piece.length:.0f}mm)", ""])

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


def generate_markdown_report(
    resource_summary: ResourceSummary,
    project_name: str = "Woodworking Project",
    standard_lengths: Optional[Dict[PieceType, List[float]]] = None,
    include_cut_diagram: bool = True,
    include_anchor_details: bool = True,
) -> str:
    """Generate a complete markdown report from ResourceSummary.

    Args:
        resource_summary: The resource summary to report on
        project_name: Name of the project
        standard_lengths: Dict mapping PieceType to available lengths in mm.
                        If None, uses sensible defaults.
        include_cut_diagram: Whether to include cut list section
        include_anchor_details: Whether to include anchor details section

    Returns:
        Complete markdown report as string

    Examples:
        >>> from nichiyou_daiku.core.piece import PieceType
        >>> from nichiyou_daiku.core.resources import ResourceSummary, PieceResource
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
        standard_lengths = _get_default_standard_lengths()

    # Generate all sections
    sections = []

    sections.append(_generate_overview_section(resource_summary, project_name))
    sections.append(_generate_bill_of_materials(resource_summary))

    # Add anchor details after BOM, before shopping list
    if include_anchor_details:
        sections.append(_generate_anchor_details(resource_summary))

    sections.append(_generate_shopping_list(resource_summary))
    sections.append(
        _generate_purchase_recommendations(resource_summary, standard_lengths)
    )

    if include_cut_diagram:
        sections.append(_generate_cut_list(resource_summary, standard_lengths))

    # Add footer
    sections.append("---\n*Report generated by nichiyou-daiku*")

    return "\n".join(sections)
