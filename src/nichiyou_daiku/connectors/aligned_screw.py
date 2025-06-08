"""Aligned wood screw connector for edge-to-edge joints.

This module implements wood screw connections where two lumber pieces
are joined along aligned edges (not face-to-face contact).
"""

from dataclasses import dataclass

from nichiyou_daiku.core.lumber import Face
from nichiyou_daiku.core.geometry import EdgePoint


@dataclass(frozen=True)
class AlignedScrewJoint:
    """Represents a wood screw joint between two aligned edges.

    This is a simple data structure that captures the essential information
    about how two lumber pieces connect via wood screws along their edges.
    The joint connects a source edge to a destination edge, where both edges
    must be aligned (running in the same direction) and share at least one
    common face.

    Attributes:
        src_face: The face that contains the source edge
        dst_face: The face that contains the destination edge
        src_edge_point: Point along the source edge where the joint connects
        dst_edge_point: Point along the destination edge where the joint connects

    Note:
        This class only represents the logical connection between edges.
        Physical details like screw positions, drill points, and assembly
        instructions are not handled at this level.

    Example:
        # Connect TOP-RIGHT edge to TOP-LEFT edge at their midpoints
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5)
        )
    """

    src_face: Face
    dst_face: Face
    src_edge_point: EdgePoint
    dst_edge_point: EdgePoint
