"""Anchor types for specifying connection points on lumber pieces.

This module defines the Anchor class and related functions for
specifying where connections occur on pieces.
"""

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
from nichiyou_daiku.core.piece import Piece, get_shape


def _get_pos_dir_edge(contact_face: Face, edge_shared_face: Face) -> Edge:
    if is_positive(cross_face(contact_face, edge_shared_face)):
        return Edge(lhs=contact_face, rhs=edge_shared_face)
    else:
        return Edge(lhs=edge_shared_face, rhs=contact_face)


class Anchor(BaseModel, frozen=True):
    """Specifies a connection point on a piece.

    An anchor defines where a connection occurs using:
    - contact_face: The face that makes contact with the other piece
    - edge_shared_face: The face that shares an edge with the contact face
    - offset: The position along the edge

    Examples:
        >>> from nichiyou_daiku.core.geometry import FromMin
        >>> anchor = Anchor(
        ...     contact_face="front",
        ...     edge_shared_face="top",
        ...     offset=FromMin(value=100)
        ... )
        >>> anchor.contact_face
        'front'
    """

    edge_shared_face: Face
    contact_face: Face
    offset: Offset


def as_edge_point(anchor: Anchor) -> EdgePoint:
    """Convert an anchor to an edge point.

    Args:
        anchor: The anchor to convert

    Returns:
        EdgePoint representing the anchor's position on the edge
    """
    return EdgePoint(
        edge=_get_pos_dir_edge(
            contact_face=anchor.contact_face,
            edge_shared_face=anchor.edge_shared_face,
        ),
        offset=anchor.offset,
    )


class BoundAnchor(BaseModel, frozen=True):
    """An anchor bound to a specific piece.

    Combines a piece with an anchor position, representing a concrete
    attachment point on a specific piece.

    Attributes:
        piece: The piece this anchor belongs to
        anchor: The anchor position specification
    """

    piece: Piece
    anchor: Anchor


def _get_box(bound: BoundAnchor) -> Box:
    """Get the Box for a BoundAnchor's piece."""
    return Box(shape=get_shape(bound.piece))


def as_surface_point(bound: BoundAnchor) -> SurfacePoint:
    """Convert a bound anchor to a surface point.

    Args:
        bound: The bound anchor to convert

    Returns:
        SurfacePoint representing the anchor's position on the piece surface
    """
    box = _get_box(bound)
    return SurfacePoint.of(box, bound.anchor.contact_face, as_edge_point(bound.anchor))


def as_point_3d(bound: BoundAnchor) -> Point3D:
    """Convert a bound anchor to a 3D point.

    Args:
        bound: The bound anchor to convert

    Returns:
        Point3D representing the anchor's position in 3D space
    """
    box = _get_box(bound)
    surface_point = as_surface_point(bound)
    return Point3D.of(box, surface_point)


def as_orientation(bound: BoundAnchor, flip_dir: bool = False) -> Orientation:
    """Get the orientation defined by a bound anchor.

    Args:
        bound: The bound anchor defining the orientation
        flip_dir: Whether to flip the up direction

    Returns:
        Orientation with direction normal to contact_face
    """
    anchor = bound.anchor
    up_face = cross_face(anchor.contact_face, anchor.edge_shared_face)
    if flip_dir:
        up_face = opposite_face(up_face)
    return Orientation.of(direction=anchor.contact_face, up=up_face)
