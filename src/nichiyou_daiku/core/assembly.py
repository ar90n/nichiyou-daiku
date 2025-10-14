"""Assembly representation for 3D visualization and construction.

This module converts the abstract model representation into concrete
3D assembly information with positions and orientations.
"""

import uuid
from pydantic import BaseModel

from .piece import get_shape
from .connection import Connection, Anchor, as_edge_point, ConnectionType
from .geometry.face import Face
from .model import Model
from .geometry import (
    Point2D,
    Point3D,
    Box,
    Orientation3D,
    cross as cross_face,
    opposite as opposite_face,
    Vector3D,
)


class SurfacePoint(BaseModel, frozen=True):
    """A point on a piece's surface.

    Represents a 2D position on a specific face of a piece.

    Attributes:
        face: The face where the point is located
        position: 2D coordinates on the face surface

    Examples:
        >>> from nichiyou_daiku.core.geometry import Point2D
        >>> sp = SurfacePoint(face="top", position=Point2D(u=50.0, v=25.0))
        >>> sp.face
        'top'
        >>> sp.position.u
        50.0
    """

    face: Face
    position: Point2D


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
        id: Unique identifier for this joint
        position: 3D position of the joint
        orientation: Full 3D orientation at the joint
        pilot_hole: Optional pilot hole specification for this joint

    Examples:
        >>> from nichiyou_daiku.core.geometry import Point3D, Vector3D, Orientation3D
        >>> joint = Joint(
        ...     id="test-joint-id",
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

    id: str
    position: Point3D
    orientation: Orientation3D
    pilot_hole: "Hole | None" = None

    @classmethod
    def of(
        cls,
        box: Box,
        anchor: Anchor,
        flip_dir: bool = False,
        joint_id: str | None = None,
        pilot_hole: "Hole | None" = None,
    ) -> "Joint":
        """Create a Joint from a piece shape and anchor point.

        Args:
            box: The 3D box of the piece
            anchor: Anchor point defining position and orientation
            flip_dir: Whether to flip the direction (for rhs joints)
            joint_id: Optional joint ID (generates UUID if not provided)
            pilot_hole: Optional pilot hole specification

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

        if joint_id is None:
            joint_id = str(uuid.uuid4())

        return cls(
            id=joint_id, position=position, orientation=orientation, pilot_hole=pilot_hole
        )


class JointPair(BaseModel, frozen=True):
    """3D connection between two pieces using joints.

    Contains the joint information for both pieces in the connection.

    Attributes:
        lhs: Joint for the base piece
        rhs: Joint for the target piece

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
        model: The source model with piece and connection definitions
        boxes: Dictionary mapping piece IDs to their 3D boxes
        joints: Dictionary mapping joint IDs to Joint objects (may include pilot_hole)
        joint_pairs: List of joint ID pairs representing connections
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
    """

    model: Model
    boxes: dict[str, Box]
    joints: dict[str, Joint]
    joint_pairs: list[tuple[str, str]]
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

        # Create joints with unique IDs
        joints: dict[str, Joint] = {}
        joint_pairs: list[tuple[str, str]] = []

        for (lhs_id, rhs_id), connection in model.connections.items():
            # Determine if pilot holes are needed
            pilot_hole = None
            if connection.type == ConnectionType.SCREW:
                # TODO: Determine proper hole specifications
                # For now, use default values
                pilot_hole = Hole(diameter=3.0, depth=None)

            # Create lhs joint
            lhs_joint = Joint.of(
                box=boxes[lhs_id],
                anchor=connection.lhs,
                flip_dir=False,
                pilot_hole=pilot_hole,
            )
            joints[lhs_joint.id] = lhs_joint

            # Create rhs joint
            rhs_joint = Joint.of(
                box=boxes[rhs_id],
                anchor=connection.rhs,
                flip_dir=True,
                pilot_hole=pilot_hole,
            )
            joints[rhs_joint.id] = rhs_joint

            # Record the pairing
            joint_pairs.append((lhs_joint.id, rhs_joint.id))

        return cls(
            model=model,
            label=model.label,
            boxes=boxes,
            joints=joints,
            joint_pairs=joint_pairs,
        )
