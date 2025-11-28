"""Connection types for joining lumber pieces.

This module defines the types used to specify how two pieces of lumber
connect to each other, including positions and orientations.
"""

from typing import TypeAlias

from pydantic import BaseModel

from nichiyou_daiku.core.anchor import Anchor
from nichiyou_daiku.core.geometry import Box, Millimeters
from nichiyou_daiku.core.piece import Piece, get_shape


class VanillaConnection(BaseModel, frozen=True):
    """A vanilla connection without special reinforcements.

    This represents a basic connection between two pieces.
    """

    pass


class DowelConnection(BaseModel, frozen=True):
    """A connection reinforced with dowels.

    This represents a connection that uses dowels for added strength.
    """

    radius: Millimeters
    depth: Millimeters


ConnectionType: TypeAlias = VanillaConnection | DowelConnection


class BoundAnchor(BaseModel, frozen=True):
    """An anchor bound to a specific piece.

    Combines a piece with an anchor position, representing a concrete
    attachment point on a specific piece.

    Attributes:
        piece: The piece this anchor belongs to
        anchor: The anchor position specification
    """

    piece: Piece
    anchor: Anchor

    def get_box(self) -> Box:
        """Get the Box for this BoundAnchor's piece.

        Returns:
            Box with the 3D shape of the piece
        """
        return Box(shape=get_shape(self.piece))


class Connection(BaseModel, frozen=True):
    """Complete connection specification between two pieces.

    Defines how a target piece connects to a base piece, using
    BoundAnchor to specify each attachment point.

    Attributes:
        base: BoundAnchor for the base piece (stays fixed)
        target: BoundAnchor for the target piece (attaches to base)
        type: Connection type (VanillaConnection or DowelConnection)
    """

    base: BoundAnchor
    target: BoundAnchor
    type: ConnectionType = VanillaConnection()
