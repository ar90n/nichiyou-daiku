"""Connection types for joining lumber pieces.

This module defines the types used to specify how two pieces of lumber
connect to each other, including positions and orientations.
"""

from typing import TypeAlias

from pydantic import BaseModel

from nichiyou_daiku.core.anchor import Anchor
from nichiyou_daiku.core.geometry import Millimeters


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


class Connection(BaseModel, frozen=True):
    """Complete connection specification between two pieces.

    Defines how a target piece connects to a base piece.
    """

    lhs: Anchor
    rhs: Anchor
    type: ConnectionType = VanillaConnection()
