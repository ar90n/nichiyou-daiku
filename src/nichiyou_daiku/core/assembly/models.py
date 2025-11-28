"""Data models for assembly joints and holes.

This module contains the core data structures for representing
joints and holes in 3D assemblies.
"""

from pydantic import BaseModel

from ..anchor import BoundAnchor
from ..geometry import (
    Face,
    Orientation3D,
    SurfacePoint,
    Vector3D,
    cross as cross_face,
    opposite as opposite_face,
)


class Hole(BaseModel, frozen=True):
    """Specification for a pilot hole.

    Attributes:
        diameter: Hole diameter in mm
        depth: Hole depth in mm (None for through-hole)

    Examples:
        >>> hole = Hole(diameter=3.0, depth=10.0)
        >>> hole.diameter
        3.0
        >>> # Through-hole
        >>> through = Hole(diameter=3.0)
        >>> through.depth is None
        True
    """

    diameter: float
    depth: float | None = None


class Joint(BaseModel, frozen=True):
    """A joint point with position and orientation.

    Represents one half of a connection between pieces.

    Attributes:
        position: Surface position of the joint
        orientation: Full 3D orientation at the joint

    Examples:
        >>> from nichiyou_daiku.core.geometry import Point2D, SurfacePoint, Vector3D, Orientation3D
        >>> joint = Joint(
        ...     position=SurfacePoint(face="top", position=Point2D(u=100.0, v=50.0)),
        ...     orientation=Orientation3D.of(
        ...         direction=Vector3D(x=0.0, y=0.0, z=1.0),
        ...         up=Vector3D(x=0.0, y=1.0, z=0.0)
        ...     )
        ... )
        >>> joint.position.face
        'top'
        >>> joint.position.position.u
        100.0
    """

    position: SurfacePoint
    orientation: Orientation3D

    @classmethod
    def of_bound_anchor(
        cls, bound_anchor: BoundAnchor, flip_dir: bool = False
    ) -> "Joint":
        """Create a Joint from a BoundAnchor.

        Args:
            bound_anchor: BoundAnchor containing piece and anchor information
            flip_dir: Whether to flip the up direction

        Returns:
            Joint with position and orientation based on the anchor
        """
        anchor = bound_anchor.anchor

        up_face = cross_face(anchor.contact_face, anchor.edge_shared_face)
        if flip_dir:
            up_face = opposite_face(up_face)
        orientation = Orientation3D.of(
            direction=Vector3D.normal_of(anchor.contact_face),
            up=Vector3D.normal_of(up_face),
        )

        position = bound_anchor.get_surface_point()
        return cls(position=position, orientation=orientation)

    @classmethod
    def of_surface_point(cls, position: SurfacePoint, up_face: Face) -> "Joint":
        orientation = Orientation3D.of(
            direction=Vector3D.normal_of(position.face),
            up=Vector3D.normal_of(up_face),
        )
        return cls(position=position, orientation=orientation)


class JointPair(BaseModel, frozen=True):
    """A pair of joints connecting two pieces."""

    lhs: Joint
    rhs: Joint
