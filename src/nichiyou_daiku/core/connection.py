"""Connection types for joining lumber pieces.

This module defines the types used to specify how two pieces of lumber
connect to each other, including positions and orientations.
"""

from enum import Enum

from pydantic import BaseModel

from nichiyou_daiku.core.geometry import (
    Box,
    Face,
    Edge,
    EdgePoint,
    SurfacePoint,
    Offset,
    Orientation,
    Point3D,
    opposite as opposite_face,
    cross as cross_face,
    is_positive,
)


class ConnectionType(Enum):
    """Enumeration of supported connection types.

    Examples:
        >>> ConnectionType.SCREW
        <ConnectionType.SCREW: 'screw'>
        >>> ConnectionType.SCREW.value
        'screw'
    """

    VANILLA = "vanilla"
    SCREW = "screw"

    @classmethod
    def of(cls, value: str) -> "ConnectionType":
        """Create a ConnectionType instance from a string value.

        Args:
            value: String representation of connection type (e.g., "screw")

        Returns:
            ConnectionType enum instance

        Raises:
            ValueError: If the connection type is not supported

        Examples:
            >>> ConnectionType.of("screw")
            <ConnectionType.SCREW: 'screw'>
            >>> ConnectionType.of("screw") == ConnectionType.SCREW
            True
            >>> import pytest
            >>> with pytest.raises(ValueError) as exc:
            ...     ConnectionType.of("bolt")
            >>> "Unsupported connection type: bolt" in str(exc.value)
            True
        """
        ret = {
            "screw": cls.SCREW,
            "vanilla": cls.VANILLA,
        }.get(value)
        if ret is not None:
            return ret

        raise ValueError(f"Unsupported connection type: {value}")


def _get_pos_dir_edge(contact_face: Face, edge_shared_face: Face) -> Edge:
    if is_positive(cross_face(contact_face, edge_shared_face)):
        return Edge(lhs=contact_face, rhs=edge_shared_face)
    else:
        return Edge(lhs=edge_shared_face, rhs=contact_face)


class Anchor(BaseModel, frozen=True):
    edge_shared_face: Face
    contact_face: Face
    offset: Offset


def as_edge_point(anchor: Anchor) -> EdgePoint:
    return EdgePoint(
        edge=_get_pos_dir_edge(
            contact_face=anchor.contact_face,
            edge_shared_face=anchor.edge_shared_face,
        ),
        offset=anchor.offset,
    )


def as_surface_point(anchor: Anchor, box: Box) -> SurfacePoint:
    return SurfacePoint.of(box, anchor.contact_face, as_edge_point(anchor))

def as_point_3d(anchor: Anchor, box: Box) -> Point3D:
    surface_point = as_surface_point(anchor, box)
    return Point3D.of(box, surface_point)

def as_orientation(anchor: Anchor, flip_dir: bool = False) -> Orientation:
    up_face = cross_face(anchor.contact_face, anchor.edge_shared_face)
    if flip_dir:
        up_face = opposite_face(up_face)
    return Orientation.of(
        direction=anchor.contact_face,
        up=up_face
    )


class Connection(BaseModel, frozen=True):
    """Complete connection specification between two pieces.

    Defines how a target piece connects to a base piece.
    """

    lhs: Anchor
    rhs: Anchor
    type: ConnectionType = ConnectionType.VANILLA
