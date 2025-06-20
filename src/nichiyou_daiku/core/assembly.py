"""Assembly representation for 3D visualization and construction.

This module converts the abstract model representation into concrete
3D assembly information with positions and orientations.
"""

from pydantic import BaseModel

from .piece import get_shape
from .connection import Connection as PieceConnection, Anchor
from .model import Model
from .geometry import Point3D, Vector3D, Box

class Joint(BaseModel, frozen=True):
    """A joint point with position and direction.

    Represents one half of a connection between pieces.

    Attributes:
        position: 3D position of the joint
        direction: Direction vector (typically unit vector)

    Examples:
        >>> joint = Joint(
        ...     position=Point3D(x=100.0, y=50.0, z=25.0),
        ...     direction=Vector3D(x=0.0, y=0.0, z=1.0)
        ... )
        >>> joint.position.x
        100.0
        >>> joint.direction.z
        1.0
    """
    position: Point3D
    direction: Vector3D

    @classmethod
    def of(cls, box: Box, anchor: Anchor) -> "Joint":
        """Create a Joint from a piece shape and anchor point.

        Args:
            shape: The 3D shape of the piece
            anchor: Anchor point defining position and direction

        Returns:
            Joint with position and direction based on the anchor
        """
        position = Point3D.of(box, anchor.edge_point)
        direction = Vector3D.normal_of(anchor.face)
        return cls(position=position, direction=direction)


class Connection(BaseModel, frozen=True):
    """3D connection between two pieces.

    Contains the joint information for both pieces in the connection.

    Attributes:
        joint1: Joint for the base piece
        joint2: Joint for the target piece

    Examples:
        >>> from nichiyou_daiku.core.piece import Piece, PieceType
        >>> from nichiyou_daiku.core.connection import (
        ...     Connection as PieceConn, BasePosition, FromTopOffset,
        ...     Anchor
        ... )
        >>> from nichiyou_daiku.core.geometry import Edge, EdgePoint
        >>> base = Piece.of(PieceType.PT_2x4, 1000.0)
        >>> target = Piece.of(PieceType.PT_2x4, 800.0)
        >>> pc = PieceConn.of(
        ...     base=BasePosition(face="top", offset=FromTopOffset(value=100)),
        ...     target=Anchor(
        ...         face="bottom",
        ...         edge_point=EdgePoint(edge=Edge(lhs="bottom", rhs="front"), value=50)
        ...     )
        ... )
        >>> base_box = Box(shape=get_shape(base))
        >>> target_box = Box(shape=get_shape(target))
        >>> conn = Connection.of(base_box, target_box, pc)
        >>> # Connection has joints with positions and directions
        >>> isinstance(conn.joint1.position, Point3D)
        True
        >>> isinstance(conn.joint2.direction, Vector3D)
        True
    """

    joint1: Joint
    joint2: Joint

    @classmethod
    def of(
        cls, base_box: Box, target_box: Box, piece_connection: PieceConnection
    ) -> "Connection":
        base_joint = Joint.of(
            box=base_box,
            anchor=piece_connection.base)
        target_joint = Joint.of(
            box=target_box,
            anchor=piece_connection.target
        )
        return cls(joint1=base_joint, joint2=target_joint)


class Assembly(BaseModel, frozen=True):
    """Complete 3D assembly with all connections.

    Represents the final assembly ready for 3D visualization.

    Attributes:
        connections: List of all 3D connections

    Examples:
        >>> from nichiyou_daiku.core.model import Model, BaseTargetPair
        >>> from nichiyou_daiku.core.piece import Piece, PieceType
        >>> from nichiyou_daiku.core.connection import (
        ...     Connection as PieceConn, BasePosition, FromTopOffset,
        ...     Anchor
        ... )
        >>> from nichiyou_daiku.core.geometry import Edge, EdgePoint
        >>> # Empty assembly
        >>> empty = Assembly(connections=[])
        >>> len(empty.connections)
        0
        >>> # Assembly from model
        >>> p1 = Piece.of(PieceType.PT_2x4, 1000.0, "p1")
        >>> p2 = Piece.of(PieceType.PT_2x4, 800.0, "p2")
        >>> pc = PieceConn.of(
        ...     base=BasePosition(face="top", offset=FromTopOffset(value=100)),
        ...     target=Anchor(
        ...         face="bottom",
        ...         edge_point=EdgePoint(edge=Edge(lhs="bottom", rhs="front"), value=50)
        ...     )
        ... )
        >>> model = Model.of(
        ...     pieces=[p1, p2],
        ...     connections=[(BaseTargetPair(base=p1, target=p2), pc)]
        ... )
        >>> assembly = Assembly.of(model)
        >>> len(assembly.connections)
        1
    """

    boxes: dict[str, Box]
    connections: dict[tuple[str, str], Connection]

    @classmethod
    def of(cls, model: Model) -> "Assembly":
        """Create an Assembly instance from a Model.

        Converts the abstract model into a concrete 3D assembly.

        Args:
            model: Model containing pieces and connections

        Returns:
            Assembly with 3D connection information
        """

        boxes = {
            piece.id: Box(shape=get_shape(piece)) for piece in model.pieces.values()
        }

        connections = {}
        for (base_id, target_id), piece_conn in model.connections.items():
            base_box = boxes[base_id]
            target_box = boxes[target_id]
            connections[(base_id, target_id)] = Connection.of(base_box, target_box, piece_conn)
        return cls(boxes=boxes, connections=connections)

