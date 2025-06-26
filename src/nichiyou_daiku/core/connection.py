"""Connection types for joining lumber pieces.

This module defines the types used to specify how two pieces of lumber
connect to each other, including positions and orientations.
"""

from typing import Literal
from pydantic import BaseModel

from nichiyou_daiku.core.geometry import Millimeters, Face, Edge, EdgePoint, cross as cross_face, orientation_from_target_to_base_coords


class FromTopOffset(BaseModel, frozen=True):
    """Offset measured from the top edge of a face.

    Examples:
        >>> offset = FromTopOffset(value=100.0)
        >>> offset.value
        100.0
        >>> # Zero is now allowed
        >>> zero_offset = FromTopOffset(value=0.0)
        >>> zero_offset.value
        0.0
        >>> # Negative values are not allowed
        >>> from pydantic import ValidationError
        >>> import pytest
        >>> with pytest.raises(ValidationError):
        ...     FromTopOffset(value=-10)
    """

    value: Millimeters


class FromBottomOffset(BaseModel, frozen=True):
    """Offset measured from the bottom edge of a face.

    Examples:
        >>> offset = FromBottomOffset(value=150.0)
        >>> offset.value
        150.0
        >>> # Different type from FromTopOffset
        >>> top = FromTopOffset(value=100.0)
        >>> bottom = FromBottomOffset(value=100.0)
        >>> type(top) != type(bottom)
        True
    """

    value: Millimeters


BaseOffset = FromTopOffset | FromBottomOffset
"""Union type for offset specifications."""


class BasePosition(BaseModel, frozen=True):
    """Position on the base piece where connection occurs.

    Attributes:
        face: Which face of the base piece (left, right, front, or back)
        offset: Distance from edge (top or bottom) of the face

    The face must be one of the four side faces. Top and bottom faces
    are not allowed as base positions because they would create ambiguous
    connection points.

    Examples:
        >>> pos = BasePosition(
        ...     face="front",
        ...     offset=FromTopOffset(value=50.0)
        ... )
        >>> pos.face
        'front'
        >>> pos.offset.value
        50.0
        >>> # Only side faces are allowed
        >>> from pydantic import ValidationError
        >>> import pytest
        >>> with pytest.raises(ValidationError):
        ...     BasePosition(face="top", offset=FromTopOffset(value=0))
    """

    face: Literal["left", "right", "front", "back"]
    offset: BaseOffset

class Anchor(BaseModel, frozen=True):
    """Anchor point on the target piece.

    Specifies where on the target piece the connection attaches.

    Attributes:
        face: Which face of the target piece
        edge_point: Position along an edge of that face

    Examples:
        >>> anchor = Anchor(
        ...     face="bottom",
        ...     edge_point=EdgePoint(edge=Edge(lhs="bottom", rhs="right"), value=10.0)
        ... )
        >>> anchor.face
        'bottom'
        >>> anchor.edge_point.value
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
        target_face_in_base_coords, target_edge_in_base_coords = orientation_from_target_to_base_coords(
            target_face=target.face,
            target_edge=target.edge_point.edge,
            base_contact_face=base.face,
            target_contact_face=target.face
        )

        # Find the non-contact face from the transformed edge to form the base edge
        base_pair_face = target_edge_in_base_coords.lhs if target_face_in_base_coords != target_edge_in_base_coords.lhs else target_edge_in_base_coords.rhs
        
        # Determine the correct edge orientation by ensuring cross product gives "top"
        if cross_face(base.face, base_pair_face) == "top":
            base_edge = Edge(lhs=base.face, rhs=base_pair_face)
        else:
            base_edge = Edge(lhs=base_pair_face, rhs=base.face)
        
        base_anchor = Anchor(
            face=base.face,
            edge_point=EdgePoint(edge=base_edge, value=base.offset.value)
        )
        return cls(base=base_anchor, target=target)
