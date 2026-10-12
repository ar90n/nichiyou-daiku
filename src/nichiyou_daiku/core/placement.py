"""Solve piece placement from connections.

Each connection fixes the target's orientation (a multiple of 90 degrees)
and its position relative to the base. Orientations are propagated exactly;
positions are solved per world axis as difference constraints, so every
accepted constraint holds exactly and contradictions are reported rather
than averaged out.
"""

from collections import deque
from collections.abc import Hashable
from typing import Literal, NamedTuple

import numpy as np
from pydantic import BaseModel

from .anchor import BoundAnchor, as_edge_point, as_point_3d
from .connection import Connection
from .geometry import (
    Box,
    Face,
    FromMax,
    FromMin,
    Point3D,
    Shape3D,
    SurfacePoint,
    Vector3D,
)
from .model import Model
from .piece import Piece, get_shape

Axis = Literal["x", "y", "z"]
ConstraintKind = Literal["rotation", "contact", "flush", "edge"]
Matrix3 = tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]
End = Literal["down", "top"]
# A point solved along one world axis: the down or top end of a piece. Along
# the axis a piece's length runs on, its two ends are separate points, tied
# by the length when it is known.
Node = tuple[str, End]

AXES: tuple[Axis, Axis, Axis] = ("x", "y", "z")
TOLERANCE_MM = 1e-6
GROUP_GAP_MM = 100.0
# Positions are rounded to 1e-6mm while extents use exact lengths, so pieces
# that only touch can share a sliver up to 2 * 5e-7mm deep.
OVERLAP_DEPTH_MM = 1e-5
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
    """Solved placement of every piece in a model."""

    poses: dict[str, Pose]
    groups: tuple[tuple[str, ...], ...]
    conflicts: tuple[Conflict, ...] = ()


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


def relative_pose(base: BoundAnchor, target: BoundAnchor) -> Pose:
    """Pose of the target in the base's local coordinates for one connection."""
    rotation = relative_rotation(base, target)
    translation = _anchor_point(base) - rotation @ _anchor_point(target)
    return Pose(
        rotation=(
            (int(rotation[0, 0]), int(rotation[0, 1]), int(rotation[0, 2])),
            (int(rotation[1, 0]), int(rotation[1, 1]), int(rotation[1, 2])),
            (int(rotation[2, 0]), int(rotation[2, 1]), int(rotation[2, 2])),
        ),
        translation=(
            float(translation[0]),
            float(translation[1]),
            float(translation[2]),
        ),
    )


def _anchor_point(bound: BoundAnchor) -> np.ndarray:
    point = as_point_3d(bound)
    return np.array([point.x, point.y, point.z])


def _axis_index(direction: np.ndarray) -> int:
    return int(np.argmax(np.abs(direction)))


def _path(adjacency: dict[str, list[str]], start: str, goal: str) -> tuple[str, ...]:
    """Shortest path from start to goal; neighbours in insertion order."""
    previous: dict[str, str | None] = {start: None}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == goal:
            break
        for neighbour in adjacency.get(node, []):
            if neighbour not in previous:
                previous[neighbour] = node
                queue.append(neighbour)
    path = [goal]
    while (step := previous.get(path[-1])) is not None:
        path.append(step)
    return tuple(reversed(path))


class _AxisOffsets:
    """Weighted union-find along one axis: offset[x] is t[x] - t[parent[x]]."""

    def __init__(self, nodes: list[Hashable]) -> None:
        self.parent: dict[Hashable, Hashable] = {node: node for node in nodes}
        self.offset: dict[Hashable, float] = {node: 0.0 for node in nodes}

    def find(self, node: Hashable) -> tuple[Hashable, float]:
        """Root of ``node`` and t[node] - t[root]."""
        path = []
        while self.parent[node] != node:
            path.append(node)
            node = self.parent[node]
        root = node
        total = 0.0
        for item in reversed(path):
            total += self.offset[item]
            self.offset[item] = total
            self.parent[item] = root
        return root, (self.offset[path[0]] if path else 0.0)

    def require(
        self, base: Hashable, target: Hashable, difference: float
    ) -> float | None:
        """Require t[target] - t[base] == difference; return the mismatch if not."""
        base_root, base_offset = self.find(base)
        target_root, target_offset = self.find(target)
        if base_root == target_root:
            mismatch = difference - (target_offset - base_offset)
            return None if abs(mismatch) <= TOLERANCE_MM else mismatch
        self.parent[target_root] = base_root
        self.offset[target_root] = difference + base_offset - target_offset
        return None


def _round(value: float) -> float:
    return round(float(value), 6) + 0.0


def _local_anchor(bound: BoundAnchor) -> tuple[np.ndarray, End]:
    """Anchor point in piece coordinates, with z measured from the piece end
    it is tied to, so the point is known even when the length is not.

    An unknown offset is taken as 0; the solver ignores the direction it
    would set.
    """
    anchor = bound.anchor
    faces = (anchor.contact_face, anchor.edge_shared_face)
    along_length = "top" not in faces and "down" not in faces
    end: End = (
        "top"
        if "top" in faces or (along_length and isinstance(anchor.offset, FromMax))
        else "down"
    )
    if anchor.offset is None:
        anchor = anchor.model_copy(update={"offset": FromMin(value=0)})
    cross_section = get_shape(bound.piece.type)
    # With a zero length the top end sits at z=0, so z is the distance from
    # whichever end the point is tied to.
    box = Box(
        shape=Shape3D(
            width=cross_section.width, height=cross_section.height, length=0.0
        )
    )
    point = Point3D.of(
        box, SurfacePoint.of(box, anchor.contact_face, as_edge_point(anchor))
    )
    return np.array([point.x, point.y, point.z]), end


def _edge_axis(rotation: np.ndarray, bound: BoundAnchor) -> int:
    """World axis the anchor's edge runs along."""
    direction = np.cross(
        _normal(bound.anchor.contact_face), _normal(bound.anchor.edge_shared_face)
    )
    return _axis_index(rotation @ direction)


class _Solution(NamedTuple):
    rotation: dict[str, np.ndarray]
    groups: list[list[str]]
    offsets: dict[Axis, _AxisOffsets]
    length_axis: dict[str, tuple[int, int]]
    conflicts: list[Conflict]


def _solve(model: Model) -> _Solution:
    """Solve orientations, then positions along each world axis.

    Connections are taken in declaration order; a constraint that contradicts
    the ones accepted before it is recorded as a conflict and ignored.
    Unknown lengths and offsets add no constraint.
    """
    piece_ids = list(model.pieces)
    rotation = {pid: np.eye(3, dtype=int) for pid in piece_ids}
    group_of = {pid: pid for pid in piece_ids}
    members = {pid: [pid] for pid in piece_ids}
    conflicts: list[Conflict] = []
    accepted: list[Connection] = []
    rotation_graph: dict[str, list[str]] = {}

    # Step 1: orientations
    for connection in model.connections.values():
        base_id, target_id = connection.base.piece.id, connection.target.piece.id
        required = rotation[base_id] @ relative_rotation(
            connection.base, connection.target
        )
        if group_of[base_id] == group_of[target_id]:
            if not np.array_equal(rotation[target_id], required):
                conflicts.append(
                    Conflict(
                        base_id=base_id,
                        target_id=target_id,
                        kind="rotation",
                        loop=_path(rotation_graph, base_id, target_id),
                    )
                )
                continue
        else:
            correction = required @ rotation[target_id].T
            moved = group_of[target_id]
            for member in members[moved]:
                rotation[member] = correction @ rotation[member]
                group_of[member] = group_of[base_id]
            members[group_of[base_id]].extend(members.pop(moved))
        accepted.append(connection)
        rotation_graph.setdefault(base_id, []).append(target_id)
        rotation_graph.setdefault(target_id, []).append(base_id)

    # Express every group in the frame of its first declared piece, so the
    # position constraints below are written in world axes.
    order = {pid: i for i, pid in enumerate(piece_ids)}
    groups = sorted(
        (sorted(group, key=order.__getitem__) for group in members.values()),
        key=lambda group: order[group[0]],
    )
    for group in groups:
        to_root = rotation[group[0]].T
        for member in group:
            rotation[member] = to_root @ rotation[member]

    # Step 2: positions, one world axis at a time. Along the axis a piece's
    # length runs on, its top end is the down end plus the length.
    nodes: list[Hashable] = [(pid, end) for pid in piece_ids for end in ("down", "top")]
    offsets: dict[Axis, _AxisOffsets] = {axis: _AxisOffsets(nodes) for axis in AXES}
    length_axis: dict[str, tuple[int, int]] = {}
    for pid, piece in model.pieces.items():
        column = rotation[pid][:, 2]
        index = _axis_index(column)
        length_axis[pid] = (index, int(column[index]))
        if piece.length is not None:
            offsets[AXES[index]].require(
                (pid, "down"), (pid, "top"), length_axis[pid][1] * piece.length
            )

    axis_graph: dict[Axis, dict[str, list[str]]] = {axis: {} for axis in AXES}
    for connection in accepted:
        base_id, target_id = connection.base.piece.id, connection.target.piece.id
        base_rot, target_rot = rotation[base_id], rotation[target_id]
        base_point, base_end = _local_anchor(connection.base)
        target_point, target_end = _local_anchor(connection.target)
        difference = base_rot @ base_point - target_rot @ target_point
        # Pieces joined by unknown offsets may slide along the shared edge
        sliding = (
            _edge_axis(base_rot, connection.base)
            if connection.base.anchor.offset is None
            else None
        )
        kinds: dict[int, ConstraintKind] = {
            _axis_index(
                base_rot @ _normal(connection.base.anchor.contact_face)
            ): "contact",
            _axis_index(
                base_rot @ _normal(connection.base.anchor.edge_shared_face)
            ): "flush",
        }
        for index, axis in enumerate(AXES):
            if index == sliding:
                continue
            base_node: Node = (
                base_id,
                base_end if index == length_axis[base_id][0] else "down",
            )
            target_node: Node = (
                target_id,
                target_end if index == length_axis[target_id][0] else "down",
            )
            mismatch = offsets[axis].require(
                base_node, target_node, float(difference[index])
            )
            if mismatch is None:
                axis_graph[axis].setdefault(base_id, []).append(target_id)
                axis_graph[axis].setdefault(target_id, []).append(base_id)
            else:
                conflicts.append(
                    Conflict(
                        base_id=base_id,
                        target_id=target_id,
                        kind=kinds.get(index, "edge"),
                        axis=axis,
                        mismatch_mm=_round(mismatch),
                        loop=_path(axis_graph[axis], base_id, target_id),
                    )
                )

    return _Solution(rotation, groups, offsets, length_axis, conflicts)


def solve_placement(model: Model) -> Placement:
    """Place every piece so that all consistent connection constraints hold.

    Connections are taken in declaration order; a constraint that contradicts
    the ones accepted before it is reported in ``conflicts`` and ignored.
    """
    rotation, groups, offsets, _, conflicts = _solve(model)

    # Step 3: positions relative to each group's first declared piece
    poses: dict[str, Pose] = {}
    for group in groups:
        root = group[0]
        root_position = np.array(
            [offsets[axis].find((root, "down"))[1] for axis in AXES]
        )
        for member in group:
            position = np.array(
                [offsets[axis].find((member, "down"))[1] for axis in AXES]
            )
            matrix = rotation[member]
            poses[member] = Pose(
                rotation=(
                    (int(matrix[0, 0]), int(matrix[0, 1]), int(matrix[0, 2])),
                    (int(matrix[1, 0]), int(matrix[1, 1]), int(matrix[1, 2])),
                    (int(matrix[2, 0]), int(matrix[2, 1]), int(matrix[2, 2])),
                ),
                translation=(
                    _round(position[0] - root_position[0]),
                    _round(position[1] - root_position[1]),
                    _round(position[2] - root_position[2]),
                ),
            )

    # Step 4: lay unconnected groups side by side along +X
    right_edge: float | None = None
    for group in groups:
        low_x = min(poses[m].bounds(model.pieces[m])[0].x for m in group)
        high_x = max(poses[m].bounds(model.pieces[m])[1].x for m in group)
        shift = 0.0 if right_edge is None else right_edge + GROUP_GAP_MM - low_x
        if shift:
            for member in group:
                x, y, z = poses[member].translation
                poses[member] = Pose(
                    rotation=poses[member].rotation,
                    translation=(_round(x + shift), y, z),
                )
        right_edge = (
            high_x + shift if right_edge is None else max(right_edge, high_x + shift)
        )

    return Placement(
        poses=poses,
        groups=tuple(tuple(group) for group in groups),
        conflicts=tuple(conflicts),
    )


def find_overlaps(model: Model, placement: Placement) -> tuple[Overlap, ...]:
    """Pairs of pieces whose boxes share volume (holes and fillets ignored)."""
    boxes = [
        (piece_id, placement.poses[piece_id].bounds(piece))
        for piece_id, piece in model.pieces.items()
    ]
    overlaps = []
    for i, (lhs, (lhs_low, lhs_high)) in enumerate(boxes):
        for rhs, (rhs_low, rhs_high) in boxes[i + 1 :]:
            sizes = (
                min(lhs_high.x, rhs_high.x) - max(lhs_low.x, rhs_low.x),
                min(lhs_high.y, rhs_high.y) - max(lhs_low.y, rhs_low.y),
                min(lhs_high.z, rhs_high.z) - max(lhs_low.z, rhs_low.z),
            )
            if all(size > OVERLAP_DEPTH_MM for size in sizes):
                volume = sizes[0] * sizes[1] * sizes[2]
                overlaps.append(Overlap(lhs=lhs, rhs=rhs, volume=volume))
    return tuple(overlaps)


def overall_bounds(model: Model, placement: Placement) -> tuple[Point3D, Point3D]:
    """Smallest world box containing every piece."""
    if not model.pieces:
        origin = Point3D(x=0.0, y=0.0, z=0.0)
        return origin, origin
    boxes = [
        placement.poses[piece_id].bounds(piece)
        for piece_id, piece in model.pieces.items()
    ]
    return (
        Point3D(
            x=min(low.x for low, _ in boxes),
            y=min(low.y for low, _ in boxes),
            z=min(low.z for low, _ in boxes),
        ),
        Point3D(
            x=max(high.x for _, high in boxes),
            y=max(high.y for _, high in boxes),
            z=max(high.z for _, high in boxes),
        ),
    )
