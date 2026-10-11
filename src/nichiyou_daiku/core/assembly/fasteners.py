"""Lay out dowels and screws inside the area where two pieces touch.

Each connection is laid out from its own relative placement, so the result
does not depend on the rest of the model. Fasteners go across the middle of
the contact rectangle's short side and at 1/4 and 3/4 of its long side (one
in the middle when there is no room for two).
"""

from typing import assert_never

import numpy as np

from ..connection import (
    Connection,
    DowelConnection,
    ScrewConnection,
    VanillaConnection,
    _get_dimension_for_face,
)
from ..geometry import Box, Face, Point3D, SurfacePoint
from ..piece import get_shape
from ..placement import _axis_index, _normal, relative_pose
from .models import Fastener, FastenerKind, Hole, LayoutIssue

CONTACT_TOLERANCE_MM = 1e-6


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
        case ScrewConnection(diameter=diameter, length=length):
            kind = "screw"
            target_thickness = _get_dimension_for_face(
                get_shape(connection.target.piece),
                connection.target.anchor.contact_face,
            )
            target_hole = Hole(diameter=diameter)
            base_hole = Hole(diameter=diameter, depth=length - target_thickness)
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

    normal = _normal(base.anchor.contact_face)
    plane_axis = _axis_index(normal)
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
    to_target = relative.rotation_matrix().T
    shift = np.array(relative.translation)
    fasteners = []
    for along in _positions_along(low[long_axis], long_size, diameter):
        point = np.zeros(3)
        point[plane_axis] = plane
        point[long_axis] = along
        point[short_axis] = low[short_axis] + short_size / 2
        fasteners.append(
            Fastener(
                base_id=base.piece.id,
                target_id=target.piece.id,
                kind=kind,
                base_position=_surface_point(base_box, base.anchor.contact_face, point),
                target_position=_surface_point(
                    target_box, target.anchor.contact_face, to_target @ (point - shift)
                ),
                base_hole=base_hole,
                target_hole=target_hole,
            )
        )
    return tuple(fasteners), None
