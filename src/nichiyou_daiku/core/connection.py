"""Connection types for joining lumber pieces.

This module defines the types used to specify how two pieces of lumber
connect to each other, including positions and orientations.
"""

from typing import Literal
from pydantic import BaseModel

from nichiyou_daiku.core.geometry import (
    Face,
    Edge,
    EdgePoint,
    cross as cross_face,
    opposite,
    Offset,
)


def _orientation_from_target_to_base_coords(
    target_face: Face,
    target_edge: Edge,
    base_contact_face: Face,
    target_contact_face: Face,
) -> tuple[Face, Edge]:
    """Transform target orientation to base coordinate system.

    When two pieces connect, this function transforms the target piece's
    orientation (face and edge) into the base piece's coordinate system.
    This ensures proper alignment when the pieces are joined.

    The transformation works by:
    1. The target contact face becomes opposite to the base contact face
    2. The edge is transformed using cross product with "top" to maintain
       consistent orientation across the connection

    Args:
        target_face: Face on the target piece (should be the contact face)
        target_edge: Edge on the target piece defining orientation
        base_contact_face: Face on the base piece where connection occurs
        target_contact_face: Face on the target piece where connection occurs

    Returns:
        Tuple of (transformed_face, transformed_edge) in base coordinates

    Raises:
        ValueError: If target_face is not part of target_edge

    Examples:
        >>> edge = Edge(lhs="bottom", rhs="back")
        >>> face, new_edge = _orientation_from_target_to_base_coords(
        ...     target_face="bottom",
        ...     target_edge=edge,
        ...     base_contact_face="top",
        ...     target_contact_face="bottom"
        ... )
        >>> face
        'bottom'
    """
    # Validate that target_face is part of target_edge
    if target_face not in (target_edge.lhs, target_edge.rhs):
        raise ValueError(
            f"Target face {target_face} is not part of the target edge {target_edge}"
        )

    # For face-to-face contact, the target face in base coords is opposite to base contact
    target_face_in_base_coords = opposite(base_contact_face)

    # Special case: when connecting top/bottom faces, preserve the edge faces directly
    if base_contact_face in ("top", "bottom") and target_contact_face in (
        "top",
        "bottom",
    ):
        # Find the non-contact face in the edge
        target_pair_face = (
            target_edge.lhs if target_face == target_edge.rhs else target_edge.rhs
        )
        target_pair_face_in_base_coords = target_pair_face
    else:
        # For other connections, use a reference face that's not on the same axis
        # This avoids the cross(top, top) issue
        if target_face_in_base_coords in ("top", "bottom"):
            reference = "front"
        elif target_face_in_base_coords in ("left", "right"):
            reference = "top"
        else:  # front/back
            reference = "top"

        if target_face == target_edge.lhs:
            # Target face is on left side - compute right side using cross product
            target_pair_face_in_base_coords = cross_face(
                reference, target_face_in_base_coords
            )
        else:
            # Target face is on right side - compute left side using cross product
            target_pair_face_in_base_coords = cross_face(
                target_face_in_base_coords, reference
            )

    # Reconstruct the edge in base coordinates preserving the relative positions
    if target_face == target_edge.lhs:
        target_edge_in_base_coords = Edge(
            lhs=target_face_in_base_coords, rhs=target_pair_face_in_base_coords
        )
    else:
        target_edge_in_base_coords = Edge(
            lhs=target_pair_face_in_base_coords, rhs=target_face_in_base_coords
        )

    return target_face_in_base_coords, target_edge_in_base_coords


class BasePosition(BaseModel, frozen=True):
    """Position on the base piece where connection occurs.

    Attributes:
        face: Which face of the base piece (left, right, front, or back)
        offset: Distance from edge (top or bottom) of the face

    The face must be one of the four side faces. Top and bottom faces
    are not allowed as base positions because they would create ambiguous
    connection points.

    Examples:
        >>> from nichiyou_daiku.core.geometry import FromMax
        >>> pos = BasePosition(
        ...     face="front",
        ...     offset=FromMax(value=50.0)
        ... )
        >>> pos.face
        'front'
        >>> pos.offset.value
        50.0
        >>> # Only side faces are allowed
        >>> from pydantic import ValidationError
        >>> import pytest
        >>> with pytest.raises(ValidationError):
        ...     BasePosition(face="top", offset=FromMax(value=0))
    """

    face: Literal["left", "right", "front", "back"]
    offset: Offset


class Anchor(BaseModel, frozen=True):
    """Anchor point on the target piece.

    Specifies where on the target piece the connection attaches.

    Attributes:
        face: Which face of the target piece
        edge_point: Position along an edge of that face

    Examples:
        >>> from nichiyou_daiku.core.geometry import Edge, EdgePoint, FromMin
        >>> anchor = Anchor(
        ...     face="bottom",
        ...     edge_point=EdgePoint(edge=Edge(lhs="bottom", rhs="right"), offset=FromMin(value=10.0))
        ... )
        >>> anchor.face
        'bottom'
        >>> anchor.edge_point.offset.value
        10.0
    """

    face: Face
    edge_point: EdgePoint


class Connection(BaseModel, frozen=True):
    """Complete connection specification between two pieces.

    Defines how a target piece connects to a base piece.
    """

    base: Anchor
    target: Anchor

    @classmethod
    def of(cls, base: BasePosition, target: Anchor) -> "Connection":
        """Create a connection from base position and target anchor.

        Args:
            base: Position on the base piece
            target: Anchor point on the target piece

        Returns:
            Connection object representing the connection
        """

        # Transform the target's orientation (face + edge) to base coordinates
        target_face_in_base_coords, target_edge_in_base_coords = (
            _orientation_from_target_to_base_coords(
                target_face=target.face,
                target_edge=target.edge_point.edge,
                base_contact_face=base.face,
                target_contact_face=target.face,
            )
        )

        # Find the non-contact face from the transformed edge to form the base edge
        base_pair_face = (
            target_edge_in_base_coords.lhs
            if target_face_in_base_coords != target_edge_in_base_coords.lhs
            else target_edge_in_base_coords.rhs
        )

        # Determine the correct edge orientation by ensuring cross product gives "top"
        if cross_face(base.face, base_pair_face) == "top":
            base_edge = Edge(lhs=base.face, rhs=base_pair_face)
        else:
            base_edge = Edge(lhs=base_pair_face, rhs=base.face)

        base_anchor = Anchor(
            face=base.face, edge_point=EdgePoint(edge=base_edge, offset=base.offset)
        )
        return cls(base=base_anchor, target=target)
