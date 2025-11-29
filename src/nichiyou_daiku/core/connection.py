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
from nichiyou_daiku.core.screw import ScrewSpec
from nichiyou_daiku.core.dowel import DowelSpec


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


class ScrewConnection(BaseModel, frozen=True):
    """A connection reinforced with screws.

    This represents a connection that uses screws for added strength.
    """

    diameter: Millimeters
    length: Millimeters


ConnectionType: TypeAlias = VanillaConnection | DowelConnection | ScrewConnection


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
        spec: DowelSpec,
    ) -> "Connection":
        """Create a dowel connection between two bound anchors.

        Args:
            base: BoundAnchor for the base piece
            target: BoundAnchor for the target piece
            spec: DowelSpec with diameter and length

        Returns:
            Connection instance representing a dowel connection

        Raises:
            ValueError: If dowel dimensions exceed piece dimensions
        """
        # Convert diameter to radius
        radius = spec.diameter / 2
        depth = spec.length

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

        # Validate diameter against cross-section
        _validate_fastener_diameter(base, target, spec.diameter, "Dowel")

        dowel_conn = DowelConnection(radius=radius, depth=depth)
        return cls(base=base, target=target, type=dowel_conn)

    @classmethod
    def of_screw(
        cls,
        base: BoundAnchor,
        target: BoundAnchor,
        spec: ScrewSpec,
    ) -> "Connection":
        """Create a screw connection between two bound anchors.

        Args:
            base: BoundAnchor for the base piece
            target: BoundAnchor for the target piece
            spec: Screw specification (diameter and length)

        Returns:
            Connection instance representing a screw connection

        Raises:
            ValueError: If screw dimensions exceed piece dimensions

        Example::

            from nichiyou_daiku.core.screw import ScrewSpec, SlimScrew, as_spec
            # Using preset screw type
            conn = Connection.of_screw(base, target, as_spec(SlimScrew.D3_3_L50))
            # Using custom spec
            conn = Connection.of_screw(base, target, ScrewSpec(diameter=4.0, length=55.0))
        """
        diameter = spec.diameter
        length = spec.length

        # Validate target contact_face is front or back
        if target.anchor.contact_face not in ("front", "back"):
            raise ValueError(
                f"ScrewConnection target contact_face must be 'front' or 'back', "
                f"got '{target.anchor.contact_face}'"
            )

        base_shape = get_shape(base.piece)
        target_shape = get_shape(target.piece)

        # Validate length against combined depth
        base_depth = _get_dimension_for_face(base_shape, base.anchor.contact_face)
        target_depth = _get_dimension_for_face(target_shape, target.anchor.contact_face)
        max_length = base_depth + target_depth

        if length > max_length:
            raise ValueError(
                f"Screw length {length}mm exceeds combined piece depth {max_length}mm"
            )

        # Validate that screw reaches base piece (must penetrate target)
        if length <= target_depth:
            raise ValueError(
                f"Screw length {length}mm does not reach base piece "
                f"(target thickness: {target_depth}mm)"
            )

        # Validate diameter against cross-section
        _validate_fastener_diameter(base, target, diameter, "Screw")

        screw_conn = ScrewConnection(diameter=diameter, length=length)
        return cls(base=base, target=target, type=screw_conn)


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


def _validate_fastener_diameter(
    base: BoundAnchor,
    target: BoundAnchor,
    diameter: float,
    fastener_type: str,
) -> None:
    """Validate that fastener diameter fits in both pieces.

    Args:
        base: BoundAnchor for the base piece
        target: BoundAnchor for the target piece
        diameter: Fastener diameter in mm
        fastener_type: Type name for error messages (e.g., "Dowel", "Screw")

    Raises:
        ValueError: If diameter exceeds cross-section of either piece
    """
    base_shape = get_shape(base.piece)
    target_shape = get_shape(target.piece)

    base_min_cross = _get_min_cross_section(base_shape, base.anchor.contact_face)
    target_min_cross = _get_min_cross_section(target_shape, target.anchor.contact_face)

    if diameter > base_min_cross:
        raise ValueError(
            f"{fastener_type} diameter {diameter}mm exceeds "
            f"base piece cross-section {base_min_cross}mm"
        )
    if diameter > target_min_cross:
        raise ValueError(
            f"{fastener_type} diameter {diameter}mm exceeds "
            f"target piece cross-section {target_min_cross}mm"
        )
