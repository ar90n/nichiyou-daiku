"""Edge types for lumber pieces.

This module provides types for representing edges formed by the intersection
of two faces on a lumber piece.
"""

from pydantic import BaseModel

from .face import Face, is_adjacent as is_adjacent_face
from .offset import Offset


class Edge(BaseModel, frozen=True):
    """Edge of a face, defined by two faces.

    Represents an edge formed by the intersection of two faces. And its direction
    is determined by the right-hand rule.

    Attributes:
        lhs: Left-hand side face
        rhs: Right-hand side face

    Examples:
        >>> edge = Edge(lhs="top", rhs="front")
        >>> edge.lhs
        'top'
        >>> edge.rhs
        'front'
    """

    lhs: Face
    rhs: Face

    def __post_init__(self):
        """Validate that lhs and rhs are adjacent faces."""
        if self.lhs == self.rhs:
            raise ValueError(
                "Left-hand side and right-hand side faces must be different."
            )
        if not is_adjacent_face(self.lhs, self.rhs):
            raise ValueError(f"Faces {self.lhs} and {self.rhs} are not adjacent.")


class EdgePoint(BaseModel, frozen=True):
    """Point along an edge defined by two faces.

    Represents a point along an edge formed by the intersection of two faces.
    The point is defined by an offset from either the minimum or maximum
    end of the edge.

    Attributes:
        edge: The edge defining the point
        offset: Offset from min or max edge end

    Examples:
        >>> from nichiyou_daiku.core.geometry import FromMin
        >>> edge_point = EdgePoint(edge=Edge(lhs="top", rhs="front"), offset=FromMin(value=50.0))
        >>> edge_point.offset.value
        50.0
    """

    edge: Edge
    offset: Offset
