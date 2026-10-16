"""The parts to make before assembling: each piece's holes in its own axes,
pieces grouped when they are made the same, and how a part drawing shows
each face. Free of build123d.

A piece's axes: x across its width, y across its thickness, z along its
length, from 0 at one corner; the down end is z = 0.
"""

from typing import NamedTuple, Sequence

import numpy as np
from pydantic import BaseModel

from nichiyou_daiku.core.geometry import Face, Point3D
from nichiyou_daiku.core.piece import get_shape
from nichiyou_daiku.core.placement import face_normal

from .builder import Assembly

FACE_ORDER: tuple[Face, ...] = ("front", "back", "left", "right", "top", "down")
LONG_FACES: tuple[Face, ...] = ("front", "back", "left", "right")
TOLERANCE_MM = 0.05
"""Holes this close are the same hole when pieces are compared."""

# The turns that bring a board onto itself: none, and half turns about z, x, y
_TURNS = (
    np.diag([1.0, 1.0, 1.0]),
    np.diag([-1.0, -1.0, 1.0]),
    np.diag([1.0, -1.0, -1.0]),
    np.diag([-1.0, 1.0, -1.0]),
)
_QUARTER = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])

# Seen from outside, a long face has its length to the right; the ends are
# turned so their width runs right on top and left on the down end
_RIGHT = {
    "front": (0.0, 0.0, 1.0),
    "back": (0.0, 0.0, 1.0),
    "left": (0.0, 0.0, 1.0),
    "right": (0.0, 0.0, 1.0),
    "top": (1.0, 0.0, 0.0),
    "down": (-1.0, 0.0, 0.0),
}

# The 8 diagonal views of the isometric, in the order ties are broken
VIEW_ORDER = (
    (1, 1, 1),
    (1, -1, 1),
    (-1, 1, 1),
    (-1, -1, 1),
    (1, 1, -1),
    (1, -1, -1),
    (-1, 1, -1),
    (-1, -1, -1),
)


class LocalHole(NamedTuple):
    """A hole in a piece's own axes; depth None is a hole drilled through."""

    face: Face
    point: tuple[float, float, float]
    diameter: float
    depth: float | None


class PartGroup(BaseModel, frozen=True):
    """Pieces made the same way; the drawing shows the first one's holes."""

    pieces: tuple[str, ...]
    size: tuple[float, float, float]
    holes: tuple[LocalHole, ...]

    @property
    def name(self) -> str:
        """The pieces, with how many when there are more than one."""
        count = len(self.pieces)
        return ", ".join(self.pieces) + (f" ×{count}" if count > 1 else "")


def piece_size(assembly: Assembly, piece_id: str) -> tuple[float, float, float]:
    """Width, thickness and length of a piece."""
    shape = get_shape(assembly.model.pieces[piece_id])
    return shape.width, shape.height, shape.length


def piece_holes(assembly: Assembly, piece_id: str) -> tuple[LocalHole, ...]:
    """The piece's holes, at their centres on the faces they are drilled into."""
    box = assembly.boxes[piece_id]
    holes = []
    for position, hole in assembly.pilot_holes.get(piece_id, []):
        point = Point3D.of(box, position)
        holes.append(
            LocalHole(
                position.face, (point.x, point.y, point.z), hole.diameter, hole.depth
            )
        )
    return tuple(holes)


def _face_along(direction: np.ndarray) -> Face:
    return next(f for f in FACE_ORDER if np.allclose(face_normal(f), direction))


def _turned(
    holes: Sequence[LocalHole], turn: np.ndarray, size: tuple[float, float, float]
) -> list[LocalHole]:
    centre = np.array(size) / 2
    turned = []
    for hole in holes:
        x, y, z = turn @ (np.array(hole.point) - centre) + centre
        turned.append(
            LocalHole(
                _face_along(turn @ face_normal(hole.face)),
                (float(x), float(y), float(z)),
                hole.diameter,
                hole.depth,
            )
        )
    return turned


def _turns(size: tuple[float, float, float]) -> list[np.ndarray]:
    """The turns that bring a board of ``size`` onto itself; a square
    section (2x2) also turns onto itself a quarter turn about its length."""
    if abs(size[0] - size[1]) > TOLERANCE_MM:
        return list(_TURNS)
    return [turn @ quarter for turn in _TURNS for quarter in (np.eye(3), _QUARTER)]


def _close(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= TOLERANCE_MM


def _same_holes(a: Sequence[LocalHole], b: Sequence[LocalHole]) -> bool:
    if len(a) != len(b):
        return False
    left = list(b)
    for hole in a:
        match = next(
            (
                other
                for other in left
                if other.face == hole.face
                and all(_close(p, q) for p, q in zip(hole.point, other.point))
                and _close(hole.diameter, other.diameter)
                and _close(hole.depth, other.depth)
            ),
            None,
        )
        if match is None:
            return False
        left.remove(match)
    return True


def part_groups(assembly: Assembly) -> list[PartGroup]:
    """The pieces grouped by how they are made, in declaration order: the
    same lumber and length, and holes that match after a turn that brings
    the board onto itself (a mirrored piece is a different part)."""
    groups: list[PartGroup] = []
    for piece_id, piece in assembly.model.pieces.items():
        size = piece_size(assembly, piece_id)
        holes = piece_holes(assembly, piece_id)
        for i, group in enumerate(groups):
            first = assembly.model.pieces[group.pieces[0]]
            if (
                first.type == piece.type
                and all(_close(p, q) for p, q in zip(group.size, size))
                and any(
                    _same_holes(group.holes, _turned(holes, turn, size))
                    for turn in _turns(size)
                )
            ):
                groups[i] = group.model_copy(
                    update={"pieces": (*group.pieces, piece_id)}
                )
                break
        else:
            groups.append(PartGroup(pieces=(piece_id,), size=size, holes=holes))
    return groups


def face_frame(face: Face) -> tuple[np.ndarray, np.ndarray]:
    """Right and up of a face seen from outside (right x up points out)."""
    right = np.array(_RIGHT[face])
    return right, np.cross(face_normal(face), right)


def face_size(face: Face, size: tuple[float, float, float]) -> tuple[float, float]:
    """Width and height of a face seen from outside."""
    right, up = face_frame(face)
    extent = np.array(size)
    return float(abs(right @ extent)), float(abs(up @ extent))


def face_point(
    face: Face, point: tuple[float, float, float], size: tuple[float, float, float]
) -> tuple[float, float]:
    """A point of the face from its lower-left corner seen from outside."""
    right, up = face_frame(face)
    extent = np.array(size)
    p = np.array(point)

    def from_corner(axis: np.ndarray) -> float:
        # The face spans 0..size on each axis, so the corner is at the minimum
        return float(p @ axis - np.minimum(axis * extent, 0).sum())

    return from_corner(right), from_corner(up)


def edge_neighbours(face: Face) -> dict[str, Face]:
    """The faces across each edge of a face seen from outside."""
    right, up = face_frame(face)
    return {
        "top": _face_along(up),
        "bottom": _face_along(-up),
        "left": _face_along(-right),
        "right": _face_along(right),
    }


def _end_turns_free(
    holes: Sequence[LocalHole], size: tuple[float, float, float]
) -> bool:
    """Whether each end's holes look the same after every turn about z that
    brings the section onto itself."""
    ends = [h for h in holes if h.face in ("top", "down")]
    return all(
        _same_holes(ends, _turned(ends, turn, size))
        for turn in _turns(size)
        if turn[2, 2] == 1.0
    )


def face_letters(
    holes: Sequence[LocalHole], size: tuple[float, float, float]
) -> dict[Face, str]:
    """A, B, ... for the drilled faces in ``FACE_ORDER``. A face without
    holes gets one only when nothing else ties the two ends' turn together:
    both ends drilled, no long face drilled and the end holes not the same
    after a turn about the length (a half turn, or a quarter turn for a
    square section); then the front is lettered too."""
    drilled: list[Face] = [f for f in FACE_ORDER if any(h.face == f for h in holes)]
    lettered: list[Face] = list(drilled)
    if (
        "top" in drilled
        and "down" in drilled
        and not any(f in LONG_FACES for f in drilled)
        and not _end_turns_free(holes, size)
    ):
        lettered.append("front")
    return {face: "ABCDEF"[i] for i, face in enumerate(lettered)}


def view_direction(faces: Sequence[Face]) -> tuple[int, int, int]:
    """The diagonal view that shows the most of ``faces``."""
    return max(
        VIEW_ORDER,
        key=lambda d: sum(1 for f in faces if face_normal(f) @ np.array(d) > 0),
    )
