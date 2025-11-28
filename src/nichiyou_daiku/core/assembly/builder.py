"""Assembly builder for creating 3D assemblies from models.

This module contains the Assembly class that orchestrates the
creation of 3D assembly information from abstract model definitions.
"""

from collections.abc import Callable

from pydantic import BaseModel

from ..connection import Connection, DowelConnection, VanillaConnection
from ..geometry import Box, Point3D
from ..model import Model
from ..piece import get_shape
from .models import Hole, Joint, JointPair
from .joints import create_vanilla_joint_pairs, create_dowel_joint_pairs


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


def _create_joint_pairs(
    base_box: Box, target_box: Box, piece_conn: Connection
) -> list[JointPair]:
    """Create joint pairs for a connection based on connection type.

    Args:
        base_box: Base piece box
        target_box: Target piece box
        piece_conn: Connection defining how pieces connect

    Returns:
        List of JointPair objects
    """
    if isinstance(piece_conn.type, VanillaConnection):
        return create_vanilla_joint_pairs(base_box, target_box, piece_conn)
    else:
        return create_dowel_joint_pairs(base_box, target_box, piece_conn)


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
        >>> from nichiyou_daiku.core.model import Model
        >>> from nichiyou_daiku.core.piece import Piece, PieceType
        >>> from nichiyou_daiku.core.anchor import Anchor
        >>> from nichiyou_daiku.core.connection import Connection
        >>> from nichiyou_daiku.core.geometry import FromMax, FromMin
        >>> # Assembly from model
        >>> p1 = Piece.of(PieceType.PT_2x4, 1000.0, "p1")
        >>> p2 = Piece.of(PieceType.PT_2x4, 800.0, "p2")
        >>> from nichiyou_daiku.core.connection import BoundAnchor
        >>> pc = Connection(
        ...     base=BoundAnchor(
        ...         piece=p1,
        ...         anchor=Anchor(
        ...             contact_face="front",
        ...             edge_shared_face="top",
        ...             offset=FromMax(value=100)
        ...         )
        ...     ),
        ...     target=BoundAnchor(
        ...         piece=p2,
        ...         anchor=Anchor(
        ...             contact_face="down",
        ...             edge_shared_face="front",
        ...             offset=FromMin(value=50)
        ...         )
        ...     )
        ... )
        >>> model = Model.of(
        ...     pieces=[p1, p2],
        ...     connections=[pc]
        ... )
        >>> assembly = Assembly.of(model)
        >>> len(assembly.joints)  # VANILLA creates 1 joint pair (2 joints)
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
        Generates pilot holes for dowel connections.

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

        for piece_conn in model.connections.values():
            base_id, target_id = piece_conn.base.piece.id, piece_conn.target.piece.id
            joint_pairs = _create_joint_pairs(
                base_box=boxes[base_id],
                target_box=boxes[target_id],
                piece_conn=piece_conn,
            )

            for joint_pair in joint_pairs:
                base_joint_id = generate_joint_id(base_id)
                target_joint_id = generate_joint_id(target_id)

                joints[base_joint_id] = joint_pair.lhs
                joints[target_joint_id] = joint_pair.rhs
                joint_conns.append((base_joint_id, target_joint_id))

                if isinstance(piece_conn.type, (DowelConnection, VanillaConnection)):
                    pilot_holes.setdefault(base_id, []).append(
                        _create_pilot_hole_on_joint(
                            box=boxes[base_id],
                            joint=joint_pair.lhs,
                        )
                    )
                    pilot_holes.setdefault(target_id, []).append(
                        _create_pilot_hole_on_joint(
                            box=boxes[target_id],
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
