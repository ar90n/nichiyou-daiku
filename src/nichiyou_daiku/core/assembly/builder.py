"""Assembly builder for creating 3D assemblies from models.

This module contains the Assembly class that orchestrates the
creation of 3D assembly information from abstract model definitions.
"""

from pydantic import BaseModel

from ..connection import ConnectionType
from ..geometry import Box, Point3D
from ..model import Model
from ..piece import get_shape
from .models import Hole, Joint
from .screw_joints import _create_joint_pairs
from .utils import _create_joint_id_generator, _create_pilot_hole_on_joint


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

                if piece_conn.type in (ConnectionType.SCREW, ConnectionType.VANILLA):
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
