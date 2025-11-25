"""Assembly representation for 3D visualization and construction.

This module converts the abstract model representation into concrete
3D assembly information with positions and orientations.
"""

from collections.abc import Callable
from pydantic import BaseModel

from .piece import get_shape
from .connection import (
    Connection,
    Anchor,
    as_point_3d,
    as_surface_point,
    as_orientation,
    ConnectionType,
)
from .model import Model
from .geometry import (
    Point2D,
    Vector2D,
    Point3D,
    Offset,
    FromMax,
    FromMin,
    Box,
    Face,
    Orientation,
    Orientation3D,
    cross as cross_face,
    opposite as opposite_face,
    Vector3D,
    SurfacePoint,
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
    def of_anchor(cls, anchor: Anchor, box: Box, flip_dir: bool = False) -> "Joint":
        """Create a Joint from a piece shape and anchor point.

        Args:
            box: The 3D box of the piece
            anchor: Anchor point defining position and orientation
            flip_dir: Whether to flip the up direction

        Returns:
            Joint with position and orientation based on the anchor
        """
        up_face = cross_face(anchor.contact_face, anchor.edge_shared_face)
        if flip_dir:
            up_face = opposite_face(up_face)
        orientation = Orientation3D.of(
            direction=Vector3D.normal_of(anchor.contact_face),
            up=Vector3D.normal_of(up_face),
        )

        position = as_surface_point(anchor, box)
        return cls(position=position, orientation=orientation)

    @classmethod
    def of_surface_point(cls, position: SurfacePoint, up_face: Face) -> "Joint":
        orientation = Orientation3D.of(
            direction=Vector3D.normal_of(position.face),
            up=Vector3D.normal_of(up_face),
        )
        return cls(position=position, orientation=orientation)


class JointPair(BaseModel, frozen=True):
    lhs: Joint
    rhs: Joint


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
        >>> src_joint = Joint.of(src_box, src_anchor)
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
        >>> orientation = Orientation.of(direction="front", up="top")
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

    import numpy as np

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


def _create_pilot_hole_on_joint(
    box: Box,
    joint: Joint,
) -> tuple[Point3D, Hole]:
    """Create a pilot hole at the joint position.

    Args:
        box: Box of the piece
        joint: Joint where the hole is to be created

    Returns:
        Tuple of (3D position of hole, Hole specification)
    """
    point_3d = Point3D.of(box, joint.position)
    hole = Hole(diameter=3.0, depth=5.0)
    return (point_3d, hole)


def _create_top_down_screw_joints(
    src_anchor: Anchor,
) -> tuple[Joint, Joint]:
    """Create two screw joints on top/down face.

    Creates joints at u=±25.4mm from face center (along width axis).

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


def _create_left_right_screw_joints(
    src_box: Box,
    dst_box: Box,
    src_anchor: Anchor,
    dst_anchor: Anchor,
) -> tuple[Joint, Joint, Joint, Joint]:
    """Create screw joints for left/right connections.

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


def _create_front_back_screw_joints_with_offset(
    src_box: Box,
    dst_box: Box,
    src_anchor: Anchor,
    dst_anchor: Anchor,
) -> tuple[Joint, Joint, Joint, Joint]:
    """Create screw joints for front/back connections with offset clamping.

    Args:
        src_box: Source piece box
        dst_box: Destination piece box
        src_anchor: Source anchor (must be front or back face with top/down edge)
        dst_anchor: Destination anchor

    Returns:
        Tuple of (src_0, src_1, dst_0, dst_1)
    """
    orientation = _create_orientation_from_anchor(src_anchor)

    # Clamp offset to prevent screws from being too close to edges
    def _anchor_offset(offset: Offset):
        match offset:
            case FromMin(value=v):
                return FromMin(value=min(v, 44.5))
            case FromMax(value=v):
                return FromMax(value=min(v, 44.5))

    # Get anchor position with clamped offset
    offset_anchor = Anchor(
        contact_face=src_anchor.contact_face,
        edge_shared_face=src_anchor.edge_shared_face,
        offset=_anchor_offset(src_anchor.offset),
    )
    anchor_sp = as_surface_point(offset_anchor, src_box)
    pos_0 = Point2D(u=25.4, v=anchor_sp.position.v)
    pos_1 = Point2D(u=-25.4, v=anchor_sp.position.v)

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


def _create_screw_joint_pairs(
    lhs_box: Box, rhs_box: Box, piece_conn: Connection
) -> list[JointPair]:
    if piece_conn.lhs.contact_face in ("down", "top"):
        lhs_0, lhs_1 = _create_top_down_screw_joints(piece_conn.lhs)
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
        rhs_0, rhs_1 = _create_top_down_screw_joints(piece_conn.rhs)
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
        lhs_0, lhs_1, rhs_0, rhs_1 = _create_left_right_screw_joints(
            src_box=lhs_box,
            dst_box=rhs_box,
            src_anchor=piece_conn.lhs,
            dst_anchor=piece_conn.rhs,
        )
        return [JointPair(lhs=lhs_0, rhs=rhs_0), JointPair(lhs=lhs_1, rhs=rhs_1)]
    elif piece_conn.rhs.contact_face in ("left", "right"):
        rhs_0, rhs_1, lhs_0, lhs_1 = _create_left_right_screw_joints(
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
            lhs_0, lhs_1, rhs_0, rhs_1 = _create_front_back_screw_joints_with_offset(
                src_box=lhs_box,
                dst_box=rhs_box,
                src_anchor=piece_conn.lhs,
                dst_anchor=piece_conn.rhs,
            )
            return [JointPair(lhs=lhs_0, rhs=rhs_0), JointPair(lhs=lhs_1, rhs=rhs_1)]
        elif is_rhs_shared_face_top_down:
            rhs_0, rhs_1, lhs_0, lhs_1 = _create_front_back_screw_joints_with_offset(
                src_box=rhs_box,
                dst_box=lhs_box,
                src_anchor=piece_conn.rhs,
                dst_anchor=piece_conn.lhs,
            )
            return [JointPair(lhs=lhs_0, rhs=rhs_0), JointPair(lhs=lhs_1, rhs=rhs_1)]
        elif is_lhs_shared_face_left_right and is_rhs_shared_face_left_right:
            raise NotImplementedError(
                "Screw joints for left-right to left-right connections are not yet implemented."
            )

        raise NotImplementedError(
            "Screw joints for front-back to front-back connections are not yet implemented."
        )
    else:
        raise RuntimeError("Unsupported screw connection configuration.")


def _create_joint_pairs(
    lhs_box: Box, rhs_box: Box, piece_conn: Connection
) -> list[JointPair]:
    return _create_screw_joint_pairs(lhs_box, rhs_box, piece_conn)


def _create_joint_id_generator(piece_ids: list[str]) -> Callable[[str], str]:
    """Create a joint ID generator function with encapsulated state.

    Returns a closure that generates sequential joint IDs for each piece.
    The counter state is encapsulated within the closure.

    Args:
        piece_ids: List of piece IDs to initialize counters for

    Returns:
        A function that generates the next joint ID for a given piece_id

    Example:
        >>> generate_id = _create_joint_id_generator(["p1", "p2"])
        >>> generate_id("p1")
        'p1_j0'
        >>> generate_id("p1")
        'p1_j1'
        >>> generate_id("p2")
        'p2_j0'
    """
    counters: dict[str, int] = {piece_id: 0 for piece_id in piece_ids}

    def generate_next(piece_id: str) -> str:
        joint_id = f"{piece_id}_j{counters[piece_id]}"
        counters[piece_id] += 1
        return joint_id

    return generate_next


class Assembly(BaseModel, frozen=True):
    """Complete 3D assembly with all joints.

    Represents the final assembly ready for 3D visualization.

    Attributes:
        model: The source model with piece and connection definitions
        boxes: Dictionary mapping piece IDs to their 3D boxes
        joints: Dictionary mapping joint IDs to Joint objects
        joint_conns: List of joint ID tuples connecting joints
        pilot_holes: Dictionary mapping piece IDs to lists of (SurfacePoint, Hole) tuples
        label: Optional label for the assembly

    Examples:
        >>> from nichiyou_daiku.core.model import Model, PiecePair
        >>> from nichiyou_daiku.core.piece import Piece, PieceType
        >>> from nichiyou_daiku.core.connection import Connection, Anchor
        >>> from nichiyou_daiku.core.geometry import FromMax, FromMin
        >>> # Assembly from model
        >>> p1 = Piece.of(PieceType.PT_2x4, 1000.0, "p1")
        >>> p2 = Piece.of(PieceType.PT_2x4, 800.0, "p2")
        >>> pc = Connection(
        ...     lhs=Anchor(
        ...         contact_face="front",
        ...         edge_shared_face="top",
        ...         offset=FromMax(value=100)
        ...     ),
        ...     rhs=Anchor(
        ...         contact_face="down",
        ...         edge_shared_face="front",
        ...         offset=FromMin(value=50)
        ...     )
        ... )
        >>> model = Model.of(
        ...     pieces=[p1, p2],
        ...     connections=[(PiecePair(base=p1, target=p2), pc)]
        ... )
        >>> assembly = Assembly.of(model)
        >>> len(assembly.joints)
        2
        >>> len(assembly.joint_conns)
        1
    """

    model: Model
    boxes: dict[str, Box]
    joints: dict[str, Joint]
    joint_conns: list[tuple[str, str]]
    pilot_holes: dict[str, list[tuple[Point3D, Hole]]]
    label: str | None

    @classmethod
    def of(cls, model: Model) -> "Assembly":
        """Create an Assembly instance from a Model.

        Converts the abstract model into a concrete 3D assembly.
        Generates pilot holes for screw connections.

        Args:
            model: Model containing pieces and connections

        Returns:
            Assembly with 3D connection information and pilot holes
        """

        boxes = {
            piece.id: Box(shape=get_shape(piece)) for piece in model.pieces.values()
        }

        # Create joints with IDs and joint pairs
        joints: dict[str, Joint] = {}
        joint_conns: list[tuple[str, str]] = []
        pilot_holes: dict[str, list[tuple[Point3D, Hole]]] = {}
        generate_joint_id = _create_joint_id_generator(list(model.pieces.keys()))

        for (lhs_id, rhs_id), piece_conn in model.connections.items():
            joint_pairs = _create_joint_pairs(
                lhs_box=boxes[lhs_id], rhs_box=boxes[rhs_id], piece_conn=piece_conn
            )

            for joint_pair in joint_pairs:
                lhs_joint_id = generate_joint_id(lhs_id)
                rhs_joint_id = generate_joint_id(rhs_id)

                joints[lhs_joint_id] = joint_pair.lhs
                joints[rhs_joint_id] = joint_pair.rhs
                joint_conns.append((lhs_joint_id, rhs_joint_id))

                if piece_conn.type == ConnectionType.SCREW or True:
                    pilot_holes.setdefault(lhs_id, []).append(
                        _create_pilot_hole_on_joint(
                            box=boxes[lhs_id],
                            joint=joint_pair.lhs,
                        )
                    )
                    pilot_holes.setdefault(rhs_id, []).append(
                        _create_pilot_hole_on_joint(
                            box=boxes[rhs_id],
                            joint=joint_pair.rhs,
                        )
                    )

        return cls(
            model=model,
            label=model.label,
            boxes=boxes,
            joints=joints,
            joint_conns=joint_conns,
            pilot_holes=pilot_holes,
        )
