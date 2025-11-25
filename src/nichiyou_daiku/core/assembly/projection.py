"""Coordinate projection functions for assembly joints.

This module provides functions for projecting joints and surface points
between different coordinate systems when connecting pieces.
"""

import numpy as np

from ..connection import Anchor, as_orientation, as_surface_point
from ..geometry import (
    Box,
    Orientation,
    Orientation3D,
    Point2D,
    SurfacePoint,
    Vector2D,
    Vector3D,
    cross as cross_face,
    opposite as opposite_face,
)
from .models import Joint


def _project_joint(
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
        >>> dst_joint = _project_joint(src_box, dst_box, src_joint, src_anchor, dst_anchor)
        >>> isinstance(dst_joint, Joint)
        True
        >>> isinstance(dst_joint.position, SurfacePoint)
        True
    """
    # Project position from src to dst coordinate system
    dst_position = _project_surface_point(
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


def _get_up_dir_aligned_axis(orientation: Orientation):
    """Determine which axis (u or v) the up direction aligns with.

    Args:
        orientation: Orientation with direction and up faces

    Returns:
        'u' if up aligns with u axis, 'v' if up aligns with v axis

    Examples:
        >>> from nichiyou_daiku.core.geometry import Orientation
        >>> orientation = Orientation.of(direction="top", up="front")
        >>> _get_up_dir_aligned_axis(orientation)
        'v'
        >>> orientation = Orientation.of(direction="front", up="left")
        >>> _get_up_dir_aligned_axis(orientation)
        'u'
    """
    match (orientation.direction, orientation.up):
        case ("top" | "down", "front" | "back"):
            return "v"
        case ("top" | "down", "left" | "right"):
            return "u"
        case ("front" | "back", "top" | "down"):
            return "v"
        case ("front" | "back", "left" | "right"):
            return "u"
        case ("left" | "right", "top" | "down"):
            return "v"
        case ("left" | "right", "front" | "back"):
            return "u"

    raise ValueError(
        f"Invalid orientation with direction {orientation.direction} and up {orientation.up}"
    )


def _need_transpose_surface_point(
    src_orientation: Orientation,
    dst_orientation: Orientation,
) -> bool:
    """Determine if surface point axes need to be transposed.

    Checks if the u and v axes of the source and destination orientations
    are aligned or need to be swapped.

    Args:
        src_orientation: Source orientation
        dst_orientation: Destination orientation
    Returns:
        True
        if axes need to be transposed, False otherwise
    Examples:
        >>> from nichiyou_daiku.core.geometry import Orientation
        >>> src_orientation = Orientation.of(direction="top", up="front")
        >>> dst_orientation = Orientation.of(direction="down", up="front")
        >>> _need_transpose_surface_point(src_orientation, dst_orientation)
        False
        >>> dst_orientation = Orientation.of(direction="down", up="left")
        >>> _need_transpose_surface_point(src_orientation, dst_orientation)
        True
    """
    src_up_axis = _get_up_dir_aligned_axis(src_orientation)
    dst_up_axis = _get_up_dir_aligned_axis(dst_orientation)

    return src_up_axis != dst_up_axis


def _project_surface_point(
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
        >>> dst_sp = _project_surface_point(src_box, dst_box, src_sp, src_anchor, dst_anchor)
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


def _project_joint_pair(
    src_box: Box,
    dst_box: Box,
    src_joint_0: Joint,
    src_joint_1: Joint,
    src_anchor: Anchor,
    dst_anchor: Anchor,
) -> tuple[Joint, Joint]:
    """Project two joints from source to destination coordinate system.

    Args:
        src_box: Source box
        dst_box: Destination box
        src_joint_0: First source joint
        src_joint_1: Second source joint
        src_anchor: Source anchor
        dst_anchor: Destination anchor

    Returns:
        Tuple of (dst_joint_0, dst_joint_1)
    """
    dst_joint_0 = _project_joint(
        src_box=src_box,
        dst_box=dst_box,
        src_joint=src_joint_0,
        src_anchor=src_anchor,
        dst_anchor=dst_anchor,
    )
    dst_joint_1 = _project_joint(
        src_box=src_box,
        dst_box=dst_box,
        src_joint=src_joint_1,
        src_anchor=src_anchor,
        dst_anchor=dst_anchor,
    )
    return (dst_joint_0, dst_joint_1)
