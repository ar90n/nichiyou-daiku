"""Connection types for joining lumber pieces.

This module defines the types used to specify how two pieces of lumber
connect to each other, including positions and orientations.
"""

from typing import TypeAlias, assert_never

from pydantic import BaseModel, model_validator

from nichiyou_daiku.core.anchor import BoundAnchor
from nichiyou_daiku.core.geometry import (
    Millimeters,
    Face,
    Shape3D,
    is_down_to_top_axis,
    is_left_to_right_axis,
    is_back_to_front_axis,
)
from nichiyou_daiku.core.piece import shape_for_checks
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

    @model_validator(mode="after")
    def _check_connection(self) -> "Connection":
        if self.base.piece.id == self.target.piece.id:
            raise ValueError(
                f"Piece '{self.base.piece.id}' cannot be connected to itself"
            )
        if (self.base.anchor.offset is None) != (self.target.anchor.offset is None):
            raise ValueError(
                "An unknown offset (?) lets the pieces slide along the shared "
                "edge, so use it on both anchors of a connection or on neither"
            )
        match self.type:
            case DowelConnection(radius=radius, depth=depth):
                _validate_dowel(self.base, self.target, radius * 2, depth)
            case ScrewConnection(diameter=diameter, length=length):
                _validate_screw(self.base, self.target, diameter, length)
            case VanillaConnection():
                pass
            case _:
                assert_never(self.type)
        return self

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
        dowel_conn = DowelConnection(radius=spec.diameter / 2, depth=spec.length)
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
        screw_conn = ScrewConnection(diameter=spec.diameter, length=spec.length)
        return cls(base=base, target=target, type=screw_conn)


def _validate_dowel(
    base: BoundAnchor, target: BoundAnchor, diameter: float, length: float
) -> None:
    # A dowel of length L is inserted L/2 into each piece; a hole as deep as
    # the piece is thick would come out on the far face.
    per_piece_depth = length / 2
    for role, bound in (("base", base), ("target", target)):
        limit = _get_dimension_for_face(
            shape_for_checks(bound.piece), bound.anchor.contact_face
        )
        if per_piece_depth >= limit:
            raise ValueError(
                f"Dowel depth {per_piece_depth}mm (half of {length}mm) would go "
                f"through the {role} piece ({limit}mm); use a dowel shorter "
                f"than {2 * limit}mm"
            )
    _validate_fastener_diameter(base, target, diameter, "Dowel")


def _validate_screw(
    base: BoundAnchor, target: BoundAnchor, diameter: float, length: float
) -> None:
    if target.anchor.contact_face not in ("front", "back"):
        raise ValueError(
            f"ScrewConnection target contact_face must be 'front' or 'back', "
            f"got '{target.anchor.contact_face}'"
        )

    base_depth = _get_dimension_for_face(
        shape_for_checks(base.piece), base.anchor.contact_face
    )
    target_depth = _get_dimension_for_face(
        shape_for_checks(target.piece), target.anchor.contact_face
    )
    max_length = base_depth + target_depth
    if length >= max_length:
        raise ValueError(
            f"Screw length {length}mm would go through the base piece; use a "
            f"screw shorter than the combined depth {max_length}mm"
        )
    if length <= target_depth:
        raise ValueError(
            f"Screw length {length}mm does not reach base piece "
            f"(target thickness: {target_depth}mm)"
        )

    _validate_fastener_diameter(base, target, diameter, "Screw")


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
    base_shape = shape_for_checks(base.piece)
    target_shape = shape_for_checks(target.piece)

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
