"""Data models for fasteners and the holes they need."""

from typing import Literal

from pydantic import BaseModel

from ..geometry import SurfacePoint


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


FastenerKind = Literal["dowel", "screw"]


class Fastener(BaseModel, frozen=True):
    """A dowel or screw joining two pieces, with the hole it needs in each.

    Attributes:
        base_id: ID of the connection's base piece
        target_id: ID of the connection's target piece (one connection per pair)
        kind: "dowel" or "screw"
        base_position: Where it enters the base, on the base's contact face
        target_position: Where it enters the target, on the target's contact face
        base_hole: Hole drilled into the base
        target_hole: Hole drilled into the target
    """

    base_id: str
    target_id: str
    kind: FastenerKind
    base_position: SurfacePoint
    target_position: SurfacePoint
    base_hole: Hole
    target_hole: Hole


class LayoutIssue(BaseModel, frozen=True):
    """A connection whose fasteners could not be laid out, or whose holes run
    into the holes of an earlier connection.

    For a collision, ``piece_id`` is the piece both holes are in, ``other`` the
    earlier connection and ``holes`` the two holes, this connection's first,
    each as where it enters the piece (piece coordinates) and how it is drilled.
    """

    base_id: str
    target_id: str
    kind: FastenerKind
    message: str
    piece_id: str | None = None
    other: tuple[str, str] | None = None
    holes: tuple[tuple[SurfacePoint, Hole], tuple[SurfacePoint, Hole]] | None = None
