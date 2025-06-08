"""Aligned wood screw connector for edge-to-edge joints.

This module implements wood screw connections where two lumber pieces
are joined along aligned edges (not face-to-face contact).
"""

from dataclasses import dataclass
from typing import List, Optional

from nichiyou_daiku.core.geometry import EdgePosition


# Type aliases
Millimeters = float
Position = float  # Position along edge (0 to length)


@dataclass(frozen=True)
class EdgeAlignment:
    """Represents how two edges align with each other.

    Attributes:
        edge1: First edge position
        edge2: Second edge position
        overlap_start: Start position of overlap on edge
        overlap_end: End position of overlap on edge
        overlap_length: Total length of overlap
    """

    edge1: EdgePosition
    edge2: EdgePosition
    overlap_start: Millimeters
    overlap_end: Millimeters
    overlap_length: Millimeters


@dataclass(frozen=True)
class DrillPoint:
    """A drilling location on an edge.

    Attributes:
        edge_position: Which edge to drill on
        position: Position along the edge (0 = start)
        diameter: Drill bit diameter in mm
        depth: Drilling depth in mm
        is_pilot: True for pilot hole, False for clearance hole
    """

    edge_position: EdgePosition
    position: Position
    diameter: Millimeters
    depth: Millimeters
    is_pilot: bool


@dataclass(frozen=True)
class AlignedScrewJoint:
    """Wood screw joint between aligned edges.

    This represents a joint where two lumber pieces are connected
    along their edges using wood screws. The pieces must share an
    edge alignment (not just face contact).

    Attributes:
        alignment: How the two edges align
        screw_diameter: Diameter of wood screws in mm
        screw_count: Number of screws to use
        pilot_diameter: Diameter of pilot holes (computed)
        drill_points: All drilling locations (computed)
    """

    edge1: EdgePosition
    edge2: EdgePosition
    overlap_start: Millimeters
    overlap_end: Millimeters
    screw_diameter: Millimeters = 4.0
    screw_count: Optional[int] = None

    def __post_init__(self):
        """Validate and compute derived properties."""
        # Validate alignment
        alignment = validate_edge_alignment(
            self.edge1,
            self.edge2,
            self.overlap_end,  # Using overlap_end as length proxy
            self.overlap_end,
            offset2=self.overlap_start,
        )
        if alignment is None:
            raise ValueError(f"Edges {self.edge1} and {self.edge2} cannot be aligned")

        # Store computed properties using object.__setattr__ due to frozen=True
        object.__setattr__(self, "alignment", alignment)
        object.__setattr__(self, "pilot_diameter", self.screw_diameter * 0.7)
        object.__setattr__(
            self,
            "drill_points",
            generate_drill_points(
                alignment, self.screw_diameter, self.pilot_diameter, self.screw_count
            ),
        )


# Functional helpers


def validate_edge_alignment(
    edge1: EdgePosition,
    edge2: EdgePosition,
    length1: Millimeters,
    length2: Millimeters,
    offset1: Millimeters = 0.0,
    offset2: Millimeters = 0.0,
    min_overlap: Millimeters = 50.0,
) -> Optional[EdgeAlignment]:
    """Check if two edges can be aligned for screw connection.

    Args:
        edge1: First edge
        edge2: Second edge
        length1: Length of first piece along edge
        length2: Length of second piece along edge
        offset1: Start position of first piece
        offset2: Start position of second piece
        min_overlap: Minimum required overlap length

    Returns:
        EdgeAlignment if valid, None otherwise

    >>> from nichiyou_daiku.core.lumber import Face
    >>> e1 = EdgePosition(Face.TOP, Face.RIGHT)
    >>> e2 = EdgePosition(Face.TOP, Face.LEFT)
    >>> align = validate_edge_alignment(e1, e2, 1000.0, 1000.0)
    >>> align.overlap_length
    1000.0
    """
    # Check if edges are compatible for alignment
    if not _are_edges_compatible(edge1, edge2):
        return None

    # Calculate overlap
    start1, end1 = offset1, offset1 + length1
    start2, end2 = offset2, offset2 + length2

    overlap_start = max(start1, start2)
    overlap_end = min(end1, end2)
    overlap_length = overlap_end - overlap_start

    # Check minimum overlap
    if overlap_length < min_overlap:
        return None

    return EdgeAlignment(
        edge1=edge1,
        edge2=edge2,
        overlap_start=overlap_start,
        overlap_end=overlap_end,
        overlap_length=overlap_length,
    )


def calculate_screw_positions(
    overlap_start: Millimeters,
    overlap_end: Millimeters,
    screw_count: Optional[int] = None,
    edge_inset: Millimeters = 50.0,
    min_spacing: Millimeters = 50.0,
    max_spacing: Millimeters = 200.0,
) -> List[Position]:
    """Calculate screw positions along an edge overlap.

    Args:
        overlap_start: Start of overlap region
        overlap_end: End of overlap region
        screw_count: Number of screws (auto-calculated if None)
        edge_inset: Minimum distance from edge ends
        min_spacing: Minimum spacing between screws
        max_spacing: Maximum spacing between screws

    Returns:
        List of positions along the edge

    >>> positions = calculate_screw_positions(0, 300, screw_count=3)
    >>> len(positions)
    3
    >>> positions[0]
    50.0
    """
    overlap_length = overlap_end - overlap_start
    usable_length = overlap_length - 2 * edge_inset

    if usable_length <= 0:
        # Too short, place single screw at center
        return [(overlap_start + overlap_end) / 2]

    # Auto-calculate screw count if not specified
    if screw_count is None:
        # Aim for ~150mm spacing
        target_spacing = 150.0
        screw_count = max(1, int(usable_length / target_spacing) + 1)

    # Adjust count to respect minimum spacing
    while screw_count > 1:
        spacing = usable_length / (screw_count - 1)
        if spacing >= min_spacing:
            break
        screw_count -= 1

    # Calculate positions
    if screw_count == 1:
        return [overlap_start + overlap_length / 2]

    positions = []
    for i in range(screw_count):
        ratio = i / (screw_count - 1)
        position = overlap_start + edge_inset + ratio * usable_length
        positions.append(position)

    return positions


def generate_drill_points(
    alignment: EdgeAlignment,
    screw_diameter: Millimeters,
    pilot_diameter: Millimeters,
    screw_count: Optional[int] = None,
    pilot_depth: Millimeters = 30.0,
    clearance_depth: Millimeters = 20.0,
) -> List[DrillPoint]:
    """Generate all drill points for an aligned screw joint.

    Args:
        alignment: Edge alignment information
        screw_diameter: Diameter of screws
        pilot_diameter: Diameter of pilot holes
        screw_count: Number of screws (auto if None)
        pilot_depth: Depth of pilot holes
        clearance_depth: Depth of clearance holes

    Returns:
        List of drill points for both pieces
    """
    # Calculate screw positions
    positions = calculate_screw_positions(
        alignment.overlap_start, alignment.overlap_end, screw_count
    )

    drill_points = []

    # Pilot holes in first piece
    for pos in positions:
        drill_points.append(
            DrillPoint(
                edge_position=alignment.edge1,
                position=pos,
                diameter=pilot_diameter,
                depth=pilot_depth,
                is_pilot=True,
            )
        )

    # Clearance holes in second piece
    for pos in positions:
        drill_points.append(
            DrillPoint(
                edge_position=alignment.edge2,
                position=pos,
                diameter=screw_diameter,
                depth=clearance_depth,
                is_pilot=False,
            )
        )

    return drill_points


def _are_edges_compatible(edge1: EdgePosition, edge2: EdgePosition) -> bool:
    """Check if two edges can be aligned together.

    Args:
        edge1: First edge
        edge2: Second edge

    Returns:
        True if edges can be aligned
    """
    # Get edge types
    type1 = edge1.get_edge_type()
    type2 = edge2.get_edge_type()

    # Edges must be of same type to align
    if type1 != type2:
        return False

    # Check specific compatibility rules based on edge type
    face_set1 = {edge1.face1, edge1.face2}
    face_set2 = {edge2.face1, edge2.face2}

    # Can't be identical edges
    if face_set1 == face_set2:
        return False

    # For aligned screw connection, edges must share exactly one face
    # Examples that work:
    # - TOP-RIGHT with TOP-LEFT (share TOP face)
    # - TOP-RIGHT with BOTTOM-RIGHT (share RIGHT face)
    # - FRONT-TOP with BACK-TOP (share TOP face)
    # Examples that DON'T work:
    # - TOP-RIGHT with FRONT-BACK (no shared faces)
    # - TOP-RIGHT with TOP-RIGHT (identical edges)

    shared_faces = face_set1 & face_set2
    return len(shared_faces) == 1
