"""Dowel joint creation functions for assembly.

This module provides functions for creating dowel joints between
pieces in different orientations (top/down, left/right, front/back).
"""

from ..connection import Anchor, Connection, as_surface_point
from ..geometry import (
    Box,
    Face,
    Orientation3D,
    Point2D,
    SurfacePoint,
    Vector2D,
    Vector3D,
    cross as cross_face,
)
from .models import Joint, JointPair
from .projection import project_joint


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
    dst_joint_0 = project_joint(
        src_box=src_box,
        dst_box=dst_box,
        src_joint=src_joint_0,
        src_anchor=src_anchor,
        dst_anchor=dst_anchor,
    )
    dst_joint_1 = project_joint(
        src_box=src_box,
        dst_box=dst_box,
        src_joint=src_joint_1,
        src_anchor=src_anchor,
        dst_anchor=dst_anchor,
    )
    return (dst_joint_0, dst_joint_1)


def _create_orientation_from_anchor(anchor: Anchor) -> Orientation3D:
    """Create orientation from anchor's contact and edge shared faces.

    Args:
        anchor: Anchor defining contact_face and edge_shared_face

    Returns:
        Orientation3D with direction normal to contact_face and up normal to crossed faces
    """
    return Orientation3D.of(
        direction=Vector3D.normal_of(anchor.contact_face),
        up=Vector3D.normal_of(cross_face(anchor.contact_face, anchor.edge_shared_face)),
    )


def _create_joint_pair_from_positions(
    face: Face,
    pos_0: Point2D,
    pos_1: Point2D,
    orientation: Orientation3D,
) -> tuple[Joint, Joint]:
    """Create two joints at specified positions on a face.

    Args:
        face: Face on which to create joints
        pos_0: Position of first joint
        pos_1: Position of second joint
        orientation: Orientation for both joints

    Returns:
        Tuple of (joint_0, joint_1)
    """
    joint_0 = Joint(
        position=SurfacePoint(
            face=face,
            position=pos_0,
        ),
        orientation=orientation,
    )
    joint_1 = Joint(
        position=SurfacePoint(
            face=face,
            position=pos_1,
        ),
        orientation=orientation,
    )
    return (joint_0, joint_1)


def _create_top_down_dowel_joints(
    src_anchor: Anchor,
) -> tuple[Joint, Joint]:
    """Create two dowel joints on top/down face.

    Creates joints at u=+/-25.4mm from face center (along width axis).

    Args:
        src_anchor: Anchor on top or down face

    Returns:
        Tuple of (joint_0, joint_1) at u=+25.4 and u=-25.4
    """
    orientation = Orientation3D.of(
        direction=Vector3D.normal_of(src_anchor.contact_face),
        up=Vector3D.normal_of(
            cross_face(src_anchor.contact_face, src_anchor.edge_shared_face)
        ),
    )

    src_0 = Joint(
        position=SurfacePoint(
            face=src_anchor.contact_face, position=Point2D(u=25.4, v=0.0)
        ),
        orientation=orientation,
    )
    src_1 = Joint(
        position=SurfacePoint(
            face=src_anchor.contact_face, position=Point2D(u=-25.4, v=0.0)
        ),
        orientation=orientation,
    )

    return (src_0, src_1)


def _create_left_right_dowel_joints(
    src_box: Box,
    dst_box: Box,
    src_anchor: Anchor,
    dst_anchor: Anchor,
) -> tuple[Joint, Joint, Joint, Joint]:
    """Create dowel joints for left/right connections.

    Args:
        src_box: Source piece box
        dst_box: Destination piece box
        src_anchor: Source anchor (must be left or right face)
        dst_anchor: Destination anchor

    Returns:
        Tuple of (src_0, src_1, dst_0, dst_1)
    """
    orientation = _create_orientation_from_anchor(src_anchor)

    # Get anchor position to place screws relative to it
    anchor_sp = as_surface_point(src_anchor, src_box)
    pos_0 = Point2D(u=0.0, v=anchor_sp.position.v + 25.4)
    pos_1 = Point2D(u=0.0, v=anchor_sp.position.v - 25.4)

    src_0, src_1 = _create_joint_pair_from_positions(
        face=src_anchor.contact_face,
        pos_0=pos_0,
        pos_1=pos_1,
        orientation=orientation,
    )
    dst_0, dst_1 = _project_joint_pair(
        src_box=src_box,
        dst_box=dst_box,
        src_joint_0=src_0,
        src_joint_1=src_1,
        src_anchor=src_anchor,
        dst_anchor=dst_anchor,
    )
    return (src_0, src_1, dst_0, dst_1)


def _create_front_back_dowel_joints_with_offset(
    src_box: Box,
    dst_box: Box,
    src_anchor: Anchor,
    dst_anchor: Anchor,
) -> tuple[Joint, Joint, Joint, Joint]:
    """Create dowel joints for front/back connections with offset clamping.

    For 2x4 lumber, dowels are placed 1 inch (25.4mm) from center horizontally,
    and 44.5mm from the anchor edge to avoid splitting.

    Args:
        src_box: Source piece box
        dst_box: Destination piece box
        src_anchor: Source anchor (must be front or back face with top/down edge)
        dst_anchor: Destination anchor

    Returns:
        Tuple of (src_0, src_1, dst_0, dst_1)
    """
    # Dowel placement constants for 2x4 lumber
    dowel_horizontal_offset = 25.4  # 1 inch from center
    dowel_edge_offset = 44.5  # Distance from anchor edge to avoid splitting

    orientation = _create_orientation_from_anchor(src_anchor)
    anchor_sp = as_surface_point(src_anchor, src_box)
    offset_dir = Vector2D.of(src_anchor.contact_face, src_anchor.edge_shared_face).v
    dowel_v = anchor_sp.position.v - offset_dir * dowel_edge_offset
    pos_0 = Point2D(u=dowel_horizontal_offset, v=dowel_v)
    pos_1 = Point2D(u=-dowel_horizontal_offset, v=dowel_v)

    src_0, src_1 = _create_joint_pair_from_positions(
        face=src_anchor.contact_face,
        pos_0=pos_0,
        pos_1=pos_1,
        orientation=orientation,
    )
    dst_0, dst_1 = _project_joint_pair(
        src_box=src_box,
        dst_box=dst_box,
        src_joint_0=src_0,
        src_joint_1=src_1,
        src_anchor=src_anchor,
        dst_anchor=dst_anchor,
    )
    return (src_0, src_1, dst_0, dst_1)


def create_vanilla_joint_pairs(
    lhs_box: Box, rhs_box: Box, piece_conn: Connection
) -> list[JointPair]:
    """Create a single joint pair at anchor positions for vanilla connections.

    Vanilla connections place one joint at each anchor point without
    the offset patterns used for screw joints.

    Args:
        lhs_box: Left-hand side piece box
        rhs_box: Right-hand side piece box
        piece_conn: Connection defining how pieces connect

    Returns:
        List containing a single JointPair at anchor positions
    """
    lhs_orientation = _create_orientation_from_anchor(piece_conn.lhs)
    lhs_surface_point = as_surface_point(piece_conn.lhs, lhs_box)

    lhs_joint = Joint(
        position=lhs_surface_point,
        orientation=lhs_orientation,
    )

    rhs_joint = project_joint(
        src_box=lhs_box,
        dst_box=rhs_box,
        src_joint=lhs_joint,
        src_anchor=piece_conn.lhs,
        dst_anchor=piece_conn.rhs,
    )

    return [JointPair(lhs=lhs_joint, rhs=rhs_joint)]


def create_dowel_joint_pairs(
    lhs_box: Box, rhs_box: Box, piece_conn: Connection
) -> list[JointPair]:
    """Create dowel joint pairs based on connection configuration.

    Args:
        lhs_box: Left-hand side piece box
        rhs_box: Right-hand side piece box
        piece_conn: Connection defining how pieces connect

    Returns:
        List of JointPair objects for dowel connections

    Raises:
        NotImplementedError: For unsupported connection configurations
        RuntimeError: For invalid connection configurations
    """
    if piece_conn.lhs.contact_face in ("down", "top"):
        lhs_0, lhs_1 = _create_top_down_dowel_joints(piece_conn.lhs)
        rhs_0, rhs_1 = _project_joint_pair(
            src_box=lhs_box,
            dst_box=rhs_box,
            src_joint_0=lhs_0,
            src_joint_1=lhs_1,
            src_anchor=piece_conn.lhs,
            dst_anchor=piece_conn.rhs,
        )
        return [JointPair(lhs=lhs_0, rhs=rhs_0), JointPair(lhs=lhs_1, rhs=rhs_1)]
    elif piece_conn.rhs.contact_face in ("down", "top"):
        rhs_0, rhs_1 = _create_top_down_dowel_joints(piece_conn.rhs)
        lhs_0, lhs_1 = _project_joint_pair(
            src_box=rhs_box,
            dst_box=lhs_box,
            src_joint_0=rhs_0,
            src_joint_1=rhs_1,
            src_anchor=piece_conn.rhs,
            dst_anchor=piece_conn.lhs,
        )
        return [JointPair(lhs=lhs_0, rhs=rhs_0), JointPair(lhs=lhs_1, rhs=rhs_1)]
    elif piece_conn.lhs.contact_face in ("left", "right"):
        lhs_0, lhs_1, rhs_0, rhs_1 = _create_left_right_dowel_joints(
            src_box=lhs_box,
            dst_box=rhs_box,
            src_anchor=piece_conn.lhs,
            dst_anchor=piece_conn.rhs,
        )
        return [JointPair(lhs=lhs_0, rhs=rhs_0), JointPair(lhs=lhs_1, rhs=rhs_1)]
    elif piece_conn.rhs.contact_face in ("left", "right"):
        rhs_0, rhs_1, lhs_0, lhs_1 = _create_left_right_dowel_joints(
            src_box=rhs_box,
            dst_box=lhs_box,
            src_anchor=piece_conn.rhs,
            dst_anchor=piece_conn.lhs,
        )
        return [JointPair(lhs=lhs_0, rhs=rhs_0), JointPair(lhs=lhs_1, rhs=rhs_1)]

    elif piece_conn.lhs.contact_face in (
        "front",
        "back",
    ) and piece_conn.rhs.contact_face in ("front", "back"):
        is_lhs_shared_face_top_down = piece_conn.lhs.edge_shared_face in ("top", "down")
        is_rhs_shared_face_top_down = piece_conn.rhs.edge_shared_face in ("top", "down")
        is_lhs_shared_face_left_right = piece_conn.lhs.edge_shared_face in (
            "left",
            "right",
        )
        is_rhs_shared_face_left_right = piece_conn.rhs.edge_shared_face in (
            "left",
            "right",
        )

        if is_lhs_shared_face_top_down:
            lhs_0, lhs_1, rhs_0, rhs_1 = _create_front_back_dowel_joints_with_offset(
                src_box=lhs_box,
                dst_box=rhs_box,
                src_anchor=piece_conn.lhs,
                dst_anchor=piece_conn.rhs,
            )
            return [JointPair(lhs=lhs_0, rhs=rhs_0), JointPair(lhs=lhs_1, rhs=rhs_1)]
        elif is_rhs_shared_face_top_down:
            rhs_0, rhs_1, lhs_0, lhs_1 = _create_front_back_dowel_joints_with_offset(
                src_box=rhs_box,
                dst_box=lhs_box,
                src_anchor=piece_conn.rhs,
                dst_anchor=piece_conn.lhs,
            )
            return [JointPair(lhs=lhs_0, rhs=rhs_0), JointPair(lhs=lhs_1, rhs=rhs_1)]
        elif is_lhs_shared_face_left_right and is_rhs_shared_face_left_right:
            raise NotImplementedError(
                "Dowel joints for left-right to left-right connections are not yet implemented."
            )

        raise NotImplementedError(
            "Dowel joints for front-back to front-back connections are not yet implemented."
        )
    else:
        raise RuntimeError("Unsupported dowel connection configuration.")
