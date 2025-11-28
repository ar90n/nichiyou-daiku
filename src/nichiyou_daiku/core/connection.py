"""Connection types for joining lumber pieces.

This module defines the types used to specify how two pieces of lumber
connect to each other, including positions and orientations.
"""

from typing import TypeAlias

from pydantic import BaseModel

from nichiyou_daiku.core.anchor import BoundAnchor
from nichiyou_daiku.core.geometry import (
    Millimeters,
    Face,
    Shape3D,
    is_down_to_top_axis,
    is_left_to_right_axis,
    is_back_to_front_axis,
)
from nichiyou_daiku.core.piece import get_shape


class VanillaConnection(BaseModel, frozen=True):
    """A vanilla connection without special reinforcements.

    This represents a basic connection between two pieces.
    """

    pass


class DowelConnection(BaseModel, frozen=True):
    """A connection reinforced with dowels.

    This represents a connection that uses dowels for added strength.
    """

    radius: Millimeters
    depth: Millimeters


ConnectionType: TypeAlias = VanillaConnection | DowelConnection


class Connection(BaseModel, frozen=True):
    """Complete connection specification between two pieces.

    Defines how a target piece connects to a base piece, using
    BoundAnchor to specify each attachment point.

    Attributes:
        base: BoundAnchor for the base piece (stays fixed)
        target: BoundAnchor for the target piece (attaches to base)
        type: Connection type (VanillaConnection or DowelConnection)
    """

    base: BoundAnchor
    target: BoundAnchor
    type: ConnectionType = VanillaConnection()

    @classmethod
    def of_vanilla(cls, base: BoundAnchor, target: BoundAnchor) -> "Connection":
        """Create a vanilla connection between two bound anchors.

        Args:
            base: BoundAnchor for the base piece
            target: BoundAnchor for the target piece

        Returns:
            Connection instance representing a vanilla connection
        """

        return cls(base=base, target=target, type=VanillaConnection())

    @classmethod
    def of_dowel(
        cls,
        base: BoundAnchor,
        target: BoundAnchor,
        radius: Millimeters,
        depth: Millimeters,
    ) -> "Connection":
        """Create a dowel connection between two bound anchors.

        Args:
            base: BoundAnchor for the base piece
            target: BoundAnchor for the target piece
            radius: Dowel radius in mm
            depth: Dowel depth in mm

        Returns:
            Connection instance representing a dowel connection

        Raises:
            ValueError: If dowel dimensions exceed piece dimensions
        """
        base_shape = get_shape(base.piece)
        target_shape = get_shape(target.piece)

        # Validate depth against contact face dimension
        base_depth_limit = _get_dimension_for_face(base_shape, base.anchor.contact_face)
        target_depth_limit = _get_dimension_for_face(
            target_shape, target.anchor.contact_face
        )

        if depth > base_depth_limit:
            raise ValueError(
                f"Dowel depth {depth}mm exceeds base piece dimension {base_depth_limit}mm"
            )
        if depth > target_depth_limit:
            raise ValueError(
                f"Dowel depth {depth}mm exceeds target piece dimension {target_depth_limit}mm"
            )

        # Validate radius against cross-section
        base_min_cross = _get_min_cross_section(base_shape, base.anchor.contact_face)
        target_min_cross = _get_min_cross_section(
            target_shape, target.anchor.contact_face
        )

        if radius * 2 > base_min_cross:
            raise ValueError(
                f"Dowel diameter {radius * 2}mm exceeds "
                f"base piece cross-section {base_min_cross}mm"
            )
        if radius * 2 > target_min_cross:
            raise ValueError(
                f"Dowel diameter {radius * 2}mm exceeds "
                f"target piece cross-section {target_min_cross}mm"
            )

        dowel_conn = DowelConnection(radius=radius, depth=depth)
        return cls(base=base, target=target, type=dowel_conn)


def _get_dimension_for_face(shape: Shape3D, face: Face) -> float:
    """Get dimension along contact face normal direction.

    Args:
        shape: 3D shape of the piece
        face: Contact face

    Returns:
        Dimension in mm along the face normal direction
    """
    # Face normal points outward, dimension is perpendicular to face
    if is_down_to_top_axis(face):  # top/down → length (Z-axis)
        return shape.length
    if is_left_to_right_axis(face):  # left/right → width (X-axis)
        return shape.width
    if is_back_to_front_axis(face):  # front/back → height (Y-axis)
        return shape.height
    raise RuntimeError("Unreachable code reached")


def _get_min_cross_section(shape: Shape3D, face: Face) -> float:
    """Get minimum cross-section dimension perpendicular to face.

    Args:
        shape: 3D shape of the piece
        face: Contact face

    Returns:
        Minimum cross-section dimension in mm
    """
    if is_down_to_top_axis(face):  # top/down → cross section is width x height
        return min(shape.width, shape.height)
    if is_left_to_right_axis(face):  # left/right → cross section is height x length
        return min(shape.height, shape.length)
    if is_back_to_front_axis(face):  # front/back → cross section is width x length
        return min(shape.width, shape.length)
    raise RuntimeError("Unreachable code reached")
