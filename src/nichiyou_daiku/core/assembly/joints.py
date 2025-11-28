"""Dowel joint creation functions for assembly.

This module provides functions for creating dowel joints between
pieces in different orientations (top/down, left/right, front/back).
"""

from ..anchor import Anchor, BoundAnchor, as_surface_point
from ..connection import Connection
from ..geometry import (
    Face,
    Orientation3D,
    Point2D,
    SurfacePoint,
    Vector2D,
    Vector3D,
    cross as cross_face,
)
from .constants import DOWEL_EDGE_OFFSET_MM, DOWEL_HORIZONTAL_OFFSET_MM
from .models import Joint, JointPair
from .projection import project_joint


def _project_joint_pair(
    src_bound: BoundAnchor,
    dst_bound: BoundAnchor,
    src_joint_0: Joint,
    src_joint_1: Joint,
) -> tuple[Joint, Joint]:
    """Project two joints from source to destination coordinate system.

    Args:
        src_bound: Source BoundAnchor
        dst_bound: Destination BoundAnchor
        src_joint_0: First source joint
        src_joint_1: Second source joint

    Returns:
        Tuple of (dst_joint_0, dst_joint_1)
    """
    dst_joint_0 = project_joint(
        src_bound=src_bound,
        dst_bound=dst_bound,
        src_joint=src_joint_0,
    )
    dst_joint_1 = project_joint(
        src_bound=src_bound,
        dst_bound=dst_bound,
        src_joint=src_joint_1,
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
            face=src_anchor.contact_face,
            position=Point2D(u=DOWEL_HORIZONTAL_OFFSET_MM, v=0.0),
        ),
        orientation=orientation,
    )
    src_1 = Joint(
        position=SurfacePoint(
            face=src_anchor.contact_face,
            position=Point2D(u=-DOWEL_HORIZONTAL_OFFSET_MM, v=0.0),
        ),
        orientation=orientation,
    )

    return (src_0, src_1)


def _create_left_right_dowel_joints(
    src_bound: BoundAnchor,
    dst_bound: BoundAnchor,
) -> tuple[Joint, Joint, Joint, Joint]:
    """Create dowel joints for left/right connections.

    Args:
        src_bound: Source BoundAnchor (must be left or right face)
        dst_bound: Destination BoundAnchor

    Returns:
        Tuple of (src_0, src_1, dst_0, dst_1)
    """
    src_anchor = src_bound.anchor

    orientation = _create_orientation_from_anchor(src_anchor)

    # Get anchor position to place screws relative to it
    anchor_sp = as_surface_point(src_bound)
    pos_0 = Point2D(u=0.0, v=anchor_sp.position.v + DOWEL_HORIZONTAL_OFFSET_MM)
    pos_1 = Point2D(u=0.0, v=anchor_sp.position.v - DOWEL_HORIZONTAL_OFFSET_MM)

    src_0, src_1 = _create_joint_pair_from_positions(
        face=src_anchor.contact_face,
        pos_0=pos_0,
        pos_1=pos_1,
        orientation=orientation,
    )
    dst_0, dst_1 = _project_joint_pair(
        src_bound=src_bound,
        dst_bound=dst_bound,
        src_joint_0=src_0,
        src_joint_1=src_1,
    )
    return (src_0, src_1, dst_0, dst_1)


def _create_front_back_dowel_joints_with_offset(
    src_bound: BoundAnchor,
    dst_bound: BoundAnchor,
) -> tuple[Joint, Joint, Joint, Joint]:
    """Create dowel joints for front/back connections with offset clamping.

    For 2x4 lumber, dowels are placed DOWEL_HORIZONTAL_OFFSET_MM from center
    horizontally, and DOWEL_EDGE_OFFSET_MM from the anchor edge to avoid splitting.

    Args:
        src_bound: Source BoundAnchor (must be front or back face with top/down edge)
        dst_bound: Destination BoundAnchor

    Returns:
        Tuple of (src_0, src_1, dst_0, dst_1)
    """
    src_anchor = src_bound.anchor

    orientation = _create_orientation_from_anchor(src_anchor)
    anchor_sp = as_surface_point(src_bound)
    offset_dir = Vector2D.of(src_anchor.contact_face, src_anchor.edge_shared_face).v
    dowel_v = anchor_sp.position.v - offset_dir * DOWEL_EDGE_OFFSET_MM
    pos_0 = Point2D(u=DOWEL_HORIZONTAL_OFFSET_MM, v=dowel_v)
    pos_1 = Point2D(u=-DOWEL_HORIZONTAL_OFFSET_MM, v=dowel_v)

    src_0, src_1 = _create_joint_pair_from_positions(
        face=src_anchor.contact_face,
        pos_0=pos_0,
        pos_1=pos_1,
        orientation=orientation,
    )
    dst_0, dst_1 = _project_joint_pair(
        src_bound=src_bound,
        dst_bound=dst_bound,
        src_joint_0=src_0,
        src_joint_1=src_1,
    )
    return (src_0, src_1, dst_0, dst_1)


def create_vanilla_joint_pairs(piece_conn: Connection) -> list[JointPair]:
    """Create a single joint pair at anchor positions for vanilla connections.

    Vanilla connections place one joint at each anchor point without
    the offset patterns used for screw joints.

    Args:
        piece_conn: Connection defining how pieces connect

    Returns:
        List containing a single JointPair at anchor positions
    """
    base_bound = piece_conn.base

    base_orientation = _create_orientation_from_anchor(base_bound.anchor)
    base_surface_point = as_surface_point(base_bound)

    base_joint = Joint(
        position=base_surface_point,
        orientation=base_orientation,
    )

    target_joint = project_joint(
        src_bound=piece_conn.base,
        dst_bound=piece_conn.target,
        src_joint=base_joint,
    )

    return [JointPair(lhs=base_joint, rhs=target_joint)]


def create_dowel_joint_pairs(piece_conn: Connection) -> list[JointPair]:
    """Create dowel joint pairs based on connection configuration.

    Args:
        piece_conn: Connection defining how pieces connect

    Returns:
        List of JointPair objects for dowel connections

    Raises:
        NotImplementedError: For unsupported connection configurations
        RuntimeError: For invalid connection configurations
    """
    base_bound = piece_conn.base
    target_bound = piece_conn.target

    if base_bound.anchor.contact_face in ("down", "top"):
        base_0, base_1 = _create_top_down_dowel_joints(base_bound.anchor)
        target_0, target_1 = _project_joint_pair(
            src_bound=base_bound,
            dst_bound=target_bound,
            src_joint_0=base_0,
            src_joint_1=base_1,
        )
        return [
            JointPair(lhs=base_0, rhs=target_0),
            JointPair(lhs=base_1, rhs=target_1),
        ]
    elif target_bound.anchor.contact_face in ("down", "top"):
        target_0, target_1 = _create_top_down_dowel_joints(target_bound.anchor)
        base_0, base_1 = _project_joint_pair(
            src_bound=target_bound,
            dst_bound=base_bound,
            src_joint_0=target_0,
            src_joint_1=target_1,
        )
        return [
            JointPair(lhs=base_0, rhs=target_0),
            JointPair(lhs=base_1, rhs=target_1),
        ]
    elif base_bound.anchor.contact_face in ("left", "right"):
        base_0, base_1, target_0, target_1 = _create_left_right_dowel_joints(
            src_bound=base_bound,
            dst_bound=target_bound,
        )
        return [
            JointPair(lhs=base_0, rhs=target_0),
            JointPair(lhs=base_1, rhs=target_1),
        ]
    elif target_bound.anchor.contact_face in ("left", "right"):
        target_0, target_1, base_0, base_1 = _create_left_right_dowel_joints(
            src_bound=target_bound,
            dst_bound=base_bound,
        )
        return [
            JointPair(lhs=base_0, rhs=target_0),
            JointPair(lhs=base_1, rhs=target_1),
        ]

    elif base_bound.anchor.contact_face in (
        "front",
        "back",
    ) and target_bound.anchor.contact_face in ("front", "back"):
        is_base_shared_face_top_down = base_bound.anchor.edge_shared_face in (
            "top",
            "down",
        )
        is_target_shared_face_top_down = target_bound.anchor.edge_shared_face in (
            "top",
            "down",
        )
        is_base_shared_face_left_right = base_bound.anchor.edge_shared_face in (
            "left",
            "right",
        )
        is_target_shared_face_left_right = target_bound.anchor.edge_shared_face in (
            "left",
            "right",
        )

        if is_base_shared_face_top_down:
            base_0, base_1, target_0, target_1 = (
                _create_front_back_dowel_joints_with_offset(
                    src_bound=base_bound,
                    dst_bound=target_bound,
                )
            )
            return [
                JointPair(lhs=base_0, rhs=target_0),
                JointPair(lhs=base_1, rhs=target_1),
            ]
        elif is_target_shared_face_top_down:
            target_0, target_1, base_0, base_1 = (
                _create_front_back_dowel_joints_with_offset(
                    src_bound=target_bound,
                    dst_bound=base_bound,
                )
            )
            return [
                JointPair(lhs=base_0, rhs=target_0),
                JointPair(lhs=base_1, rhs=target_1),
            ]
        elif is_base_shared_face_left_right and is_target_shared_face_left_right:
            raise NotImplementedError(
                "Dowel joints for left-right to left-right connections are not yet implemented."
            )

        raise NotImplementedError(
            "Dowel joints for front-back to front-back connections are not yet implemented."
        )
    else:
        raise RuntimeError("Unsupported dowel connection configuration.")
