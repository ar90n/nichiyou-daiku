"""Assembly representation for 3D visualization and construction.

This module converts the abstract model representation into concrete
3D assembly information with positions and orientations.
"""

from pydantic import BaseModel

from .piece import get_shape
from .connection import Connection, Anchor, as_edge_point
from .model import Model
from .geometry import (
    Point3D,
    Box,
    Orientation3D,
    cross as cross_face,
    opposite as opposite_face,
    Vector3D,
)


class Joint(BaseModel, frozen=True):
    """A joint point with position and orientation.

    Represents one half of a connection between pieces.

    Attributes:
        position: 3D position of the joint
        orientation: Full 3D orientation at the joint

    Examples:
        >>> from nichiyou_daiku.core.geometry import Point3D, Vector3D, Orientation3D
        >>> joint = Joint(
        ...     position=Point3D(x=100.0, y=50.0, z=25.0),
        ...     orientation=Orientation3D.of(
        ...         direction=Vector3D(x=0.0, y=0.0, z=1.0),
        ...         up=Vector3D(x=0.0, y=1.0, z=0.0)
        ...     )
        ... )
        >>> joint.position.x
        100.0
        >>> joint.orientation.direction.z
        1.0
    """

    position: Point3D
    orientation: Orientation3D

    @classmethod
    def of(cls, box: Box, anchor: Anchor, flip_dir: bool = False) -> "Joint":
        """Create a Joint from a piece shape and anchor point.

        Args:
            box: The 3D box of the piece
            anchor: Anchor point defining position and orientation

        Returns:
            Joint with position and orientation based on the anchor
        """
        up_face = cross_face(anchor.contact_face, anchor.edge_shared_face)
        if flip_dir:
            up_face = opposite_face(up_face)

        position = Point3D.of(box, as_edge_point(anchor))
        orientation = Orientation3D.of(
            direction=Vector3D.normal_of(anchor.contact_face),
            up=Vector3D.normal_of(up_face),
        )
        return cls(position=position, orientation=orientation)


class JointPair(BaseModel, frozen=True):
    """3D connection between two pieces using joints.

    Contains the joint information for both pieces in the connection.

    Attributes:
        joint1: Joint for the base piece
        joint2: Joint for the target piece

    Examples:
        >>> from nichiyou_daiku.core.piece import Piece, PieceType
        >>> from nichiyou_daiku.core.connection import Connection, Anchor
        >>> from nichiyou_daiku.core.geometry import FromMax, FromMin
        >>> base = Piece.of(PieceType.PT_2x4, 1000.0)
        >>> target = Piece.of(PieceType.PT_2x4, 800.0)
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
        >>> base_box = Box(shape=get_shape(base))
        >>> target_box = Box(shape=get_shape(target))
        >>> conn = JointPair.of(base_box, target_box, pc)
        >>> # JointPair has joints with positions and orientations
        >>> isinstance(conn.lhs.position, Point3D)
        True
        >>> isinstance(conn.rhs.orientation, Orientation3D)
        True
    """

    lhs: Joint
    rhs: Joint

    @classmethod
    def of(
        cls, lhs_box: Box, rhs_box: Box, piece_connection: Connection
    ) -> "JointPair":
        return cls(
            lhs=Joint.of(box=lhs_box, anchor=piece_connection.lhs),
            rhs=Joint.of(box=rhs_box, anchor=piece_connection.rhs, flip_dir=True),
        )


class Assembly(BaseModel, frozen=True):
    """Complete 3D assembly with all joints.

    Represents the final assembly ready for 3D visualization.

    Attributes:
        boxes: Dictionary mapping piece IDs to their 3D boxes
        joints: Dictionary mapping piece ID pairs to their joint pairs
        label: Optional label for the assembly

    Examples:
        >>> from nichiyou_daiku.core.model import Model, PiecePair
        >>> from nichiyou_daiku.core.piece import Piece, PieceType
        >>> from nichiyou_daiku.core.connection import Connection, Anchor
        >>> from nichiyou_daiku.core.geometry import FromMax, FromMin
        >>> # Empty assembly
        >>> empty = Assembly(boxes={}, joints={}, label="empty")
        >>> len(empty.joints)
        0
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
        1
    """

    boxes: dict[str, Box]
    joints: dict[tuple[str, str], JointPair]
    label: str | None

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
        joints = {
            (lhs_id, rhs_id): JointPair.of(boxes[lhs_id], boxes[rhs_id], piece_conn)
            for (lhs_id, rhs_id), piece_conn in model.connections.items()
        }
        return cls(label=model.label, boxes=boxes, joints=joints)
