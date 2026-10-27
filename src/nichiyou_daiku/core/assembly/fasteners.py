"""Lay out dowels and screws inside the area where two pieces touch.

Each connection is laid out from its own relative placement, so the result
does not depend on the rest of the model. Fasteners go across the middle of
the contact rectangle's short side and at 1/4 and 3/4 of its long side (one
in the middle when there is no room for two).
"""

from collections.abc import Mapping, Sequence
from itertools import combinations
from typing import NamedTuple, assert_never

import numpy as np

from ..connection import (
    Connection,
    DowelConnection,
    ScrewConnection,
    VanillaConnection,
    _get_dimension_for_face,
)
from ..geometry import Box, Face, Point3D, SurfacePoint, opposite
from ..piece import Piece, get_shape
from ..placement import axis_index, face_normal, relative_pose
from .models import Fastener, FastenerKind, Hole, LayoutIssue

CONTACT_TOLERANCE_MM = 1e-6


def pilot_diameter(screw_diameter: float) -> float:
    """Pilot hole for a screw: about 65% of the screw, to the nearest 0.5mm
    and at least 0.5mm.

    A hole as wide as the screw would leave its thread nothing to bite.

    >>> [pilot_diameter(d) for d in (3.3, 3.8, 4.2)]
    [2.0, 2.5, 2.5]
    """
    return max(0.5, round(screw_diameter * 0.65 * 2) / 2)


def counterbore_diameter(screw_diameter: float) -> float:
    """Counterbore for a screw head to sink into: 10mm, or 12mm for screws
    thicker than 4.5mm.

    >>> [counterbore_diameter(d) for d in (3.8, 4.5, 5.2)]
    [10.0, 10.0, 12.0]
    """
    return 10.0 if screw_diameter <= 4.5 else 12.0


def _positions_along(start: float, length: float, diameter: float) -> list[float]:
    if length / 2 >= 2 * diameter:
        return [start + length / 4, start + 3 * length / 4]
    return [start + length / 2]


def _surface_point(box: Box, face: Face, point: np.ndarray) -> SurfacePoint:
    return SurfacePoint.from_point(
        box, face, Point3D(x=float(point[0]), y=float(point[1]), z=float(point[2]))
    )


def layout_fasteners(
    connection: Connection,
) -> tuple[tuple[Fastener, ...], LayoutIssue | None]:
    """Fasteners for one connection, or the reason they do not fit."""
    kind: FastenerKind
    connection_type = connection.type
    match connection_type:
        case DowelConnection(radius=radius, depth=length):
            kind = "dowel"
            diameter = radius * 2
            base_hole = target_hole = Hole(diameter=diameter, depth=length / 2)
            sunk = 0.0
        case ScrewConnection(diameter=diameter, length=length):
            kind = "screw"
            # Through a narrow face the head sinks into a counterbore, so the
            # screw crosses the target's thickness either way
            target_shape = get_shape(connection.target.piece)
            target_thickness = target_shape.height
            sunk = (
                _get_dimension_for_face(
                    target_shape, connection.target.anchor.contact_face
                )
                - target_thickness
            )
            pilot = pilot_diameter(diameter)
            target_hole = Hole(diameter=pilot)
            base_hole = Hole(diameter=pilot, depth=length - target_thickness)
        case VanillaConnection():
            return (), None
        case _:
            assert_never(connection_type)

    base, target = connection.base, connection.target
    base_shape = get_shape(base.piece)
    base_high = np.array([base_shape.width, base_shape.height, base_shape.length])
    relative = relative_pose(base, target)
    target_low, target_high = relative.bounds(target.piece)
    low = np.maximum(np.zeros(3), [target_low.x, target_low.y, target_low.z])
    high = np.minimum(base_high, [target_high.x, target_high.y, target_high.z])

    normal = face_normal(base.anchor.contact_face)
    plane_axis = axis_index(normal)
    plane = base_high[plane_axis] if normal[plane_axis] > 0 else 0.0
    first, second = (axis for axis in range(3) if axis != plane_axis)
    sizes = {first: high[first] - low[first], second: high[second] - low[second]}

    def issue(message: str) -> LayoutIssue:
        return LayoutIssue(
            base_id=base.piece.id, target_id=target.piece.id, kind=kind, message=message
        )

    if min(sizes.values()) <= CONTACT_TOLERANCE_MM:
        return (), issue("pieces do not share a contact area")
    long_axis, short_axis = (
        (first, second) if sizes[first] >= sizes[second] else (second, first)
    )
    long_size, short_size = sizes[long_axis], sizes[short_axis]
    if short_size < 2 * diameter:
        return (), issue(
            f"contact area {short_size:.1f} x {long_size:.1f}mm is too narrow "
            f"for a {diameter:.1f}mm {kind} (needs {2 * diameter:.1f}mm)"
        )

    base_box = Box(shape=base_shape)
    target_box = Box(shape=get_shape(target.piece))
    target_size = np.array(
        [target_box.shape.width, target_box.shape.height, target_box.shape.length]
    )
    to_target = relative.rotation_matrix().T
    shift = np.array(relative.translation)
    fasteners = []
    for along in _positions_along(low[long_axis], long_size, diameter):
        point = np.zeros(3)
        point[plane_axis] = plane
        point[long_axis] = along
        point[short_axis] = low[short_axis] + short_size / 2
        target_point = to_target @ (point - shift)
        counterbore = None
        if sunk > 0:
            far = opposite(target.anchor.contact_face)
            far_axis = axis_index(face_normal(far))
            far_point = target_point.copy()
            far_point[far_axis] = (
                0.0 if face_normal(far)[far_axis] < 0 else target_size[far_axis]
            )
            counterbore = (
                _surface_point(target_box, far, far_point),
                Hole(diameter=counterbore_diameter(diameter), depth=sunk),
            )
        fasteners.append(
            Fastener(
                base_id=base.piece.id,
                target_id=target.piece.id,
                kind=kind,
                diameter=diameter,
                base_position=_surface_point(base_box, base.anchor.contact_face, point),
                target_position=_surface_point(
                    target_box, target.anchor.contact_face, target_point
                ),
                base_hole=base_hole,
                target_hole=target_hole,
                counterbore=counterbore,
            )
        )
    return tuple(fasteners), None


class _Bore(NamedTuple):
    """A drilled hole in piece coordinates: a cylinder along one axis."""

    axis: int
    low: float
    high: float
    center: np.ndarray
    radius: float


def _bore(box: Box, position: SurfacePoint, hole: Hole) -> _Bore:
    entry = Point3D.of(box, position)
    center = np.array([entry.x, entry.y, entry.z])
    normal = face_normal(position.face)
    axis = axis_index(normal)
    size = (box.shape.width, box.shape.height, box.shape.length)[axis]
    end = center[axis] - normal[axis] * (size if hole.depth is None else hole.depth)
    low, high = sorted((float(center[axis]), float(end)))
    return _Bore(axis, low, high, center, hole.diameter / 2)


def _gap(value: float, low: float, high: float) -> float:
    return max(low - value, 0.0, value - high)


def _bores_meet(a: _Bore, b: _Bore) -> bool:
    if a.axis == b.axis:
        across = np.delete(a.center - b.center, a.axis)
        return (
            min(a.high, b.high) - max(a.low, b.low) > CONTACT_TOLERANCE_MM
            and float(np.hypot(*across)) < a.radius + b.radius - CONTACT_TOLERANCE_MM
        )
    # Perpendicular bores come closest where each is nearest the other's axis.
    gap_a = _gap(float(b.center[a.axis]), a.low, a.high)
    gap_b = _gap(float(a.center[b.axis]), b.low, b.high)
    if (
        gap_a >= b.radius - CONTACT_TOLERANCE_MM
        or gap_b >= a.radius - CONTACT_TOLERANCE_MM
    ):
        return False
    third = 3 - a.axis - b.axis
    reach = np.sqrt(a.radius**2 - gap_b**2) + np.sqrt(b.radius**2 - gap_a**2)
    return bool(abs(a.center[third] - b.center[third]) < reach - CONTACT_TOLERANCE_MM)


def find_hole_collisions(
    fasteners: Sequence[Fastener], pieces: Mapping[str, Piece]
) -> list[LayoutIssue]:
    """Holes of two connections that run into each other inside a piece.

    Reported once on the later of the two connections, in the order of
    ``fasteners``; the fasteners themselves are kept. Holes of one connection
    are not compared: a screw runs inside its own counterbore, and the layout
    spaces fasteners at least two diameters apart.
    Judged on the space each fastener takes (its own diameter over the hole's
    depth): a screw is wider than its pilot hole. A counterbore takes its own
    width.
    """
    bores: dict[str, list[tuple[Fastener, SurfacePoint, Hole, _Bore]]] = {}
    for fastener in fasteners:
        drilled = [
            (
                fastener.base_id,
                fastener.base_position,
                Hole(diameter=fastener.diameter, depth=fastener.base_hole.depth),
            ),
            (
                fastener.target_id,
                fastener.target_position,
                Hole(diameter=fastener.diameter, depth=fastener.target_hole.depth),
            ),
        ]
        if fastener.counterbore is not None:
            drilled.append((fastener.target_id, *fastener.counterbore))
        for piece_id, position, space in drilled:
            box = Box(shape=get_shape(pieces[piece_id]))
            bores.setdefault(piece_id, []).append(
                (fastener, position, space, _bore(box, position, space))
            )

    issues: dict[tuple[str, str, str, str], LayoutIssue] = {}
    for piece_id, drilled in bores.items():
        for (earlier, earlier_at, earlier_hole, a), (
            later,
            later_at,
            later_hole,
            b,
        ) in combinations(drilled, 2):
            same = (earlier.base_id, earlier.target_id) == (
                later.base_id,
                later.target_id,
            )
            if same or not _bores_meet(a, b):
                continue
            issues.setdefault(
                (later.base_id, later.target_id, earlier.base_id, earlier.target_id),
                LayoutIssue(
                    base_id=later.base_id,
                    target_id=later.target_id,
                    kind=later.kind,
                    message=(
                        f"{later.kind} hole in '{piece_id}' runs into a "
                        f"{earlier.kind} hole of connection "
                        f"{earlier.base_id} -> {earlier.target_id}"
                    ),
                    piece_id=piece_id,
                    other=(earlier.base_id, earlier.target_id),
                    holes=((later_at, later_hole), (earlier_at, earlier_hole)),
                ),
            )
    return list(issues.values())
