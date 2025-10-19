"""Assembly representation for 3D visualization and construction.

This module converts the abstract model representation into concrete
3D assembly information with positions and orientations.
"""

from collections.abc import Callable
from pydantic import BaseModel

from .piece import get_shape
from .connection import Connection, Anchor, as_edge_point, ConnectionType
from .model import Model
from .geometry import (
    Point2D,
    Point3D,
    Box,
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
    def of(cls, box: Box, anchor: Anchor, flip_dir: bool = False) -> "Joint":
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

        position = SurfacePoint.of(box, anchor.contact_face, as_edge_point(anchor))
        orientation = Orientation3D.of(
            direction=Vector3D.normal_of(anchor.contact_face),
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
    # Step 1: Convert source SurfacePoint to Point3D in source coordinate system
    src_point_3d = Point3D.of(src_box, src_surface_point)

    # Step 2: Get the joint positions for both anchors
    src_joint = Joint.of(src_box, src_anchor)
    dst_joint = Joint.of(dst_box, dst_anchor, flip_dir=True)

    # Step 3: Transform from src to dst coordinate system
    # Get the 3D positions of both joints
    src_joint_3d = Point3D.of(src_box, src_joint.position)
    dst_joint_3d = Point3D.of(dst_box, dst_joint.position)

    # Calculate the relative position from src_joint to src_point
    rel_x = src_point_3d.x - src_joint_3d.x
    rel_y = src_point_3d.y - src_joint_3d.y
    rel_z = src_point_3d.z - src_joint_3d.z

    # Transform the relative position using the orientation difference
    # For now, we implement a simplified version that assumes
    # the coordinate systems align when anchors match
    # TODO: Implement full rotation transformation using orientation matrices

    # Calculate dst point in dst coordinate system
    dst_point_3d = Point3D(
        x=dst_joint_3d.x + rel_x,
        y=dst_joint_3d.y + rel_y,
        z=dst_joint_3d.z + rel_z,
    )

    # Step 4: Project the 3D point onto the destination face
    # We need to convert Point3D to SurfacePoint on the destination contact face
    face = dst_anchor.contact_face

    # Project the 3D point onto the 2D face coordinates
    if face in ("top", "down"):
        u = dst_point_3d.x - dst_box.shape.width / 2
        v = dst_point_3d.y - dst_box.shape.height / 2
    elif face in ("left", "right"):
        u = dst_point_3d.y - dst_box.shape.height / 2
        v = dst_point_3d.z - dst_box.shape.length / 2
    elif face in ("front", "back"):
        u = dst_point_3d.x - dst_box.shape.width / 2
        v = dst_point_3d.z - dst_box.shape.length / 2
    else:
        raise ValueError(f"Invalid face: {face}")

    return SurfacePoint(face=face, position=Point2D(u=u, v=v))


def _calculate_pilot_holes_for_connection(
    lhs_box: Box,
    rhs_box: Box,
    connection: Connection,
) -> tuple[list[tuple[SurfacePoint, Hole]], list[tuple[SurfacePoint, Hole]]]:
    """Calculate pilot holes for both sides of a connection.

    This function converts a Connection specification into pilot hole positions
    for both the lhs and rhs pieces.

    Args:
        lhs_box: Box for the lhs piece
        rhs_box: Box for the rhs piece
        connection: Connection specification

    Returns:
        Tuple of (lhs_holes, rhs_holes) where each is a list of (SurfacePoint, Hole)

    Note:
        This is a stub implementation. The actual logic will be implemented
        to convert Anchor positions to SurfacePoint coordinates.
    """
    # Stub implementation - returns empty lists
    # TODO: Implement actual conversion from Connection to pilot holes
    return ([], [])


def _create_vanilla_joint_pairs(
    lhs_box: Box, rhs_box: Box, piece_conn: Connection
) -> list[JointPair]:
    lhs = Joint.of(box=lhs_box, anchor=piece_conn.lhs)
    rhs = _project_joint(
        src_box=lhs_box,
        dst_box=rhs_box,
        src_joint=lhs,
        src_anchor=piece_conn.lhs,
        dst_anchor=piece_conn.rhs,
    )

    return [JointPair(lhs=lhs, rhs=rhs)]


def _create_screw_joint_pairs(
    lhs_box: Box, rhs_box: Box, piece_conn: Connection
) -> list[JointPair]:
    lhs = Joint.of(box=lhs_box, anchor=piece_conn.lhs)
    rhs = _project_joint(
        src_box=lhs_box,
        dst_box=rhs_box,
        src_joint=lhs,
        src_anchor=piece_conn.lhs,
        dst_anchor=piece_conn.rhs,
    )

    return [JointPair(lhs=lhs, rhs=rhs)]


def _create_joint_pairs(
    lhs_box: Box, rhs_box: Box, piece_conn: Connection
) -> list[JointPair]:
    match piece_conn.type:
        case ConnectionType.VANILLA:
            return _create_vanilla_joint_pairs(lhs_box, rhs_box, piece_conn)
        case ConnectionType.SCREW:
            return _create_screw_joint_pairs(lhs_box, rhs_box, piece_conn)

    raise RuntimeError(f"Unhandled connection type: {piece_conn.type}")


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
    pilot_holes: dict[str, list[tuple[SurfacePoint, Hole]]]
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

        # Generate pilot holes for screw connections
        pilot_holes: dict[str, list[tuple[SurfacePoint, Hole]]] = {}
        for (lhs_id, rhs_id), connection in model.connections.items():
            if connection.type == ConnectionType.SCREW:
                lhs_holes, rhs_holes = _calculate_pilot_holes_for_connection(
                    boxes[lhs_id], boxes[rhs_id], connection
                )

                if lhs_holes:
                    if lhs_id not in pilot_holes:
                        pilot_holes[lhs_id] = []
                    pilot_holes[lhs_id].extend(lhs_holes)

                if rhs_holes:
                    if rhs_id not in pilot_holes:
                        pilot_holes[rhs_id] = []
                    pilot_holes[rhs_id].extend(rhs_holes)

        return cls(
            model=model,
            label=model.label,
            boxes=boxes,
            joints=joints,
            joint_conns=joint_conns,
            pilot_holes=pilot_holes,
        )
