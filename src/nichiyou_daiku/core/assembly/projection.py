"""Coordinate projection functions for assembly joints.

This module provides functions for projecting joints and surface points
between different coordinate systems when connecting pieces.
"""

import numpy as np

from ..connection import Anchor, as_orientation, as_surface_point
from ..geometry import (
    Box,
    Orientation3D,
    Point2D,
    SurfacePoint,
    Vector2D,
    Vector3D,
    cross as cross_face,
    opposite as opposite_face,
)
from .models import Joint


def project_joint(
    src_box: Box,
    dst_box: Box,
    src_joint: Joint,
    src_anchor: Anchor,
    dst_anchor: Anchor,
) -> Joint:
    """Project a joint from source to destination coordinate system.

    Transforms a Joint from one piece's coordinate system to another piece's
    coordinate system when the two pieces are connected via matching anchors.

    This function projects the joint's position and calculates the appropriate
    orientation for the destination piece.

    Args:
        src_box: Box of the source piece
        dst_box: Box of the destination piece
        src_joint: Joint in source coordinate system
        src_anchor: Source anchor
        dst_anchor: Destination anchor (must match with src_anchor)

    Returns:
        Joint in destination coordinate system with projected position
        and calculated orientation

    Examples:
        >>> from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
        >>> from nichiyou_daiku.core.geometry import FromMax, FromMin
        >>> # Create two pieces
        >>> src_piece = Piece.of(PieceType.PT_2x4, 1000.0)
        >>> dst_piece = Piece.of(PieceType.PT_2x4, 800.0)
        >>> src_box = Box(shape=get_shape(src_piece))
        >>> dst_box = Box(shape=get_shape(dst_piece))
        >>> # Create matching anchors
        >>> src_anchor = Anchor(contact_face="front", edge_shared_face="top", offset=FromMax(value=100))
        >>> dst_anchor = Anchor(contact_face="down", edge_shared_face="front", offset=FromMin(value=50))
        >>> # Create and project joint
        >>> src_joint = Joint.of_anchor(src_anchor, src_box)
        >>> dst_joint = project_joint(src_box, dst_box, src_joint, src_anchor, dst_anchor)
        >>> isinstance(dst_joint, Joint)
        True
        >>> isinstance(dst_joint.position, SurfacePoint)
        True
    """
    # Project position from src to dst coordinate system
    dst_position = project_surface_point(
        src_box=src_box,
        dst_box=dst_box,
        src_surface_point=src_joint.position,
        src_anchor=src_anchor,
        dst_anchor=dst_anchor,
    )

    # Calculate orientation for dst (same logic as Joint.of with flip_dir=True)
    up_face = cross_face(dst_anchor.contact_face, dst_anchor.edge_shared_face)
    up_face = opposite_face(up_face)  # flip_dir=True

    dst_orientation = Orientation3D.of(
        direction=Vector3D.normal_of(dst_anchor.contact_face),
        up=Vector3D.normal_of(up_face),
    )

    return Joint(position=dst_position, orientation=dst_orientation)


def project_surface_point(
    src_box: Box,
    dst_box: Box,
    src_surface_point: SurfacePoint,
    src_anchor: Anchor,
    dst_anchor: Anchor,
) -> SurfacePoint:
    """Project a surface point from source to destination coordinate system.

    Transforms a SurfacePoint from one piece's coordinate system to another
    piece's coordinate system when the two pieces are connected via matching anchors.

    This function assumes that src_anchor and dst_anchor represent matching
    connection points (i.e., they are at the same position in 3D space when
    the pieces are assembled).

    Args:
        src_box: Box of the source piece
        dst_box: Box of the destination piece
        src_surface_point: Surface point in source coordinate system
        src_anchor: Source anchor
        dst_anchor: Destination anchor (must match with src_anchor)

    Returns:
        Surface point in destination coordinate system

    Examples:
        >>> from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
        >>> from nichiyou_daiku.core.geometry import Point2D, FromMax, FromMin
        >>> # Create two pieces
        >>> src_piece = Piece.of(PieceType.PT_2x4, 1000.0)
        >>> dst_piece = Piece.of(PieceType.PT_2x4, 800.0)
        >>> src_box = Box(shape=get_shape(src_piece))
        >>> dst_box = Box(shape=get_shape(dst_piece))
        >>> # Create matching anchors
        >>> src_anchor = Anchor(contact_face="front", edge_shared_face="top", offset=FromMax(value=100))
        >>> dst_anchor = Anchor(contact_face="down", edge_shared_face="front", offset=FromMin(value=50))
        >>> # Project a point from src to dst
        >>> src_sp = SurfacePoint(face="front", position=Point2D(u=10.0, v=20.0))
        >>> dst_sp = project_surface_point(src_box, dst_box, src_sp, src_anchor, dst_anchor)
        >>> isinstance(dst_sp, SurfacePoint)
        True
    """
    src_anchor_orientation = as_orientation(src_anchor)
    dst_anchor_orientation = as_orientation(dst_anchor, flip_dir=True)

    src_anchor_contact_dir = Vector2D.of(
        src_anchor.contact_face, src_anchor.edge_shared_face
    )
    src_anchor_up_dir = Vector2D.of(src_anchor.contact_face, src_anchor_orientation.up)
    dst_anchor_contact_dir = Vector2D.of(
        dst_anchor.contact_face, dst_anchor.edge_shared_face
    )
    dst_anchor_up_up = Vector2D.of(dst_anchor.contact_face, dst_anchor_orientation.up)

    src_mat = np.array(
        [
            [src_anchor_contact_dir.u, src_anchor_contact_dir.v],
            [src_anchor_up_dir.u, src_anchor_up_dir.v],
        ]
    )
    dst_mat = np.array(
        [
            [dst_anchor_contact_dir.u, dst_anchor_contact_dir.v],
            [dst_anchor_up_up.u, dst_anchor_up_up.v],
        ]
    )
    tr_mat = np.linalg.inv(dst_mat) @ src_mat
    transpose_axes = abs(np.diag(tr_mat).prod()) < 1e-7
    flip_u = tr_mat[:, 0].min() < 0
    flip_v = tr_mat[:, 1].min() < 0

    src_anchor_surface_point = as_surface_point(src_anchor, src_box)
    dst_anchor_surface_point = as_surface_point(dst_anchor, dst_box)

    rel_u = src_surface_point.position.u - src_anchor_surface_point.position.u
    rel_v = src_surface_point.position.v - src_anchor_surface_point.position.v

    if flip_u:
        rel_u = -rel_u
    if flip_v:
        rel_v = -rel_v
    if transpose_axes:
        rel_u, rel_v = rel_v, rel_u

    return SurfacePoint(
        face=dst_anchor.contact_face,
        position=Point2D(
            u=dst_anchor_surface_point.position.u + rel_u,
            v=dst_anchor_surface_point.position.v + rel_v,
        ),
    )
