"""Connection types for joining lumber pieces.

This module defines the types used to specify how two pieces of lumber
connect to each other, including positions and orientations.
"""

from pydantic import BaseModel

from nichiyou_daiku.core.geometry import Millimeters, Face, Edge, EdgePoint, cross as cross_face, face_from_target_to_base_coords


class FromTopOffset(BaseModel, frozen=True):
    """Offset measured from the top edge of a face.

    Examples:
        >>> offset = FromTopOffset(value=100.0)
        >>> offset.value
        100.0
        >>> # Must be positive
        >>> from pydantic import ValidationError
        >>> import pytest
        >>> with pytest.raises(ValidationError):
        ...     FromTopOffset(value=0)
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
        face: Which face of the base piece
        offset: Distance from face (top or bottom)

    If face is "top" or "bottom", the offset is meaningless because the
    position is already defined by the face itself. However, it is included
    for consistency with other position types.

    Examples:
        >>> pos = BasePosition(
        ...     face="top",
        ...     offset=FromTopOffset(value=50.0)
        ... )
        >>> pos.face
        'top'
        >>> pos.offset.value
        50.0
        >>> # Immutable
        >>> from pydantic import ValidationError
        >>> import pytest
        >>> with pytest.raises(ValidationError):
        ...     pos.face = "bottom"
    """

    face: Face
    offset: BaseOffset

class Anchor(BaseModel, frozen=True):
    """Anchor point on the target piece.

    Specifies where on the target piece the connection attaches.

    Attributes:
        face: Which face of the target piece
        edge_position: Position along an edge of that face

    Examples:
        >>> anchor = TargetAnchor(
        ...     face="bottom",
        ...     edge_position=EdgePosition(src="bottom", dst="right", value=10.0)
        ... )
        >>> anchor.face
        'bottom'
        >>> anchor.edge_position.value
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

        # Step 1: Get target edge direction from cross product of edge faces
        target_edge_dir = cross_face(target.edge_point.edge.lhs, target.edge_point.edge.rhs)
        
        # Step 2: Transform target edge direction to base coordinates
        base_edge_dir = face_from_target_to_base_coords(target_edge_dir, base.face, target.face)
        
        # Step 3: Find base pair face using cross product
        base_pair_face = cross_face(base.face, base_edge_dir)

        if isinstance(base.offset, FromTopOffset):
            base_edge_point = EdgePoint(
                edge=Edge(
                    lhs = base_pair_face,
                    rhs = base.face
                ),
                value=base.offset.value
            )
        else:  # FromBottomOffset
            base_edge_point = EdgePoint(
                edge=Edge(
                    lhs = base.face,
                    rhs = base_pair_face
                ),
                value=base.offset.value
            )

        base_anchor = Anchor(face=base.face, edge_point=base_edge_point)
        return cls(base=base_anchor, target=target)
