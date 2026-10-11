"""Solve piece placement from connections.

Each connection fixes the target's orientation (a multiple of 90 degrees)
and its position relative to the base. Orientations are propagated exactly;
positions are solved per world axis as difference constraints, so every
accepted constraint holds exactly and contradictions are reported rather
than averaged out.
"""

from typing import Literal

import numpy as np
from pydantic import BaseModel

from .anchor import BoundAnchor
from .geometry import Face, Point3D, Vector3D
from .piece import Piece, get_shape

Axis = Literal["x", "y", "z"]
ConstraintKind = Literal["rotation", "contact", "flush", "edge"]
Matrix3 = tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]

AXES: tuple[Axis, Axis, Axis] = ("x", "y", "z")
TOLERANCE_MM = 1e-6
GROUP_GAP_MM = 100.0
IDENTITY: Matrix3 = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


class Pose(BaseModel, frozen=True):
    """Where a piece sits in the world: a 90-degree rotation and a translation.

    A local point p maps to ``rotation @ p + translation``.
    """

    rotation: Matrix3 = IDENTITY
    translation: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def rotation_matrix(self) -> np.ndarray:
        return np.array(self.rotation, dtype=float)

    def apply(self, point: Point3D) -> Point3D:
        x, y, z = self.rotation_matrix() @ np.array(
            [point.x, point.y, point.z]
        ) + np.array(self.translation)
        return Point3D(x=float(x), y=float(y), z=float(z))

    def bounds(self, piece: Piece) -> tuple[Point3D, Point3D]:
        """World axis-aligned bounding box of the piece."""
        shape = get_shape(piece)
        corners = np.array(
            [
                [x, y, z]
                for x in (0.0, shape.width)
                for y in (0.0, shape.height)
                for z in (0.0, shape.length)
            ]
        )
        world = corners @ self.rotation_matrix().T + np.array(self.translation)
        low, high = world.min(axis=0), world.max(axis=0)
        return (
            Point3D(x=float(low[0]), y=float(low[1]), z=float(low[2])),
            Point3D(x=float(high[0]), y=float(high[1]), z=float(high[2])),
        )


class Conflict(BaseModel, frozen=True):
    """A connection constraint that contradicts the ones accepted before it.

    ``loop`` is the path of pieces from base to target through the accepted
    constraints that the conflicting one would close.
    """

    base_id: str
    target_id: str
    kind: ConstraintKind
    axis: Axis | None = None
    mismatch_mm: float | None = None
    loop: tuple[str, ...]


class Placement(BaseModel, frozen=True):
    """Solved placement of every piece in a model.

    ``free_axes`` lists, per piece, the world axes along which nothing ties
    it to its group's first piece. Current connections constrain all three
    axes, so it is empty.
    """

    poses: dict[str, Pose]
    groups: tuple[tuple[str, ...], ...]
    conflicts: tuple[Conflict, ...] = ()
    free_axes: dict[str, frozenset[Axis]] = {}


class Overlap(BaseModel, frozen=True):
    """Two pieces whose boxes share volume (mm³)."""

    lhs: str
    rhs: str
    volume: float


def _normal(face: Face) -> np.ndarray:
    v = Vector3D.normal_of(face)
    return np.array([v.x, v.y, v.z])


def _frame(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    return np.column_stack([first, second, np.cross(first, second)])


def relative_rotation(base: BoundAnchor, target: BoundAnchor) -> np.ndarray:
    """Rotation taking target-local directions to base-local directions.

    The contact faces face each other and the edge-shared faces face the
    same way (flush).
    """
    n_base = _normal(base.anchor.contact_face)
    e_base = _normal(base.anchor.edge_shared_face)
    n_target = _normal(target.anchor.contact_face)
    e_target = _normal(target.anchor.edge_shared_face)
    rotation = _frame(-n_base, e_base) @ _frame(n_target, e_target).T
    return np.rint(rotation).astype(int)
