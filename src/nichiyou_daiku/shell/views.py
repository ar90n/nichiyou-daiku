"""The four directions a model is drawn from, and where piece labels go.

Shared by the technical drawing and the check image. Free of build123d: the
projection is the one build123d's ``project_to_viewport`` uses when looking at
the origin, so a label placed here lands on the projected lines.
"""

from typing import NamedTuple, Sequence

import numpy as np

from nichiyou_daiku.core.assembly import Assembly

# A ray that only grazes a face or an edge of a box is not hidden by it
_TOLERANCE_MM = 1e-6


class View(NamedTuple):
    """A viewing direction and its place on a 2x2 sheet (column and row
    counted from the top left)."""

    caption: str
    origin: tuple[float, float, float]
    up: tuple[float, float, float]
    column: int
    row: int


# The order is the order the technical drawing writes its edges in
VIEWS = (
    View("from +z", (0, 0, 100), (0, 1, 0), 0, 0),
    View("from -y", (0, -100, 0), (0, 0, 1), 0, 1),
    View("from +x +y +z", (100, 100, 100), (0, 0, 1), 1, 0),
    View("from +x", (100, 0, 0), (0, 0, 1), 1, 1),
)


class Label(NamedTuple):
    """A piece ID at a point of the viewport."""

    piece_id: str
    x: float
    y: float


def _unit(vector: Sequence[float] | np.ndarray) -> np.ndarray:
    v = np.asarray(vector, dtype=float)
    return v / np.linalg.norm(v)


def project(view: View, point: Sequence[float]) -> tuple[float, float]:
    """Viewport coordinates of a world point, as build123d projects it."""
    toward_viewer = _unit(view.origin)
    up = np.asarray(view.up, dtype=float)
    up = _unit(up - up.dot(toward_viewer) * toward_viewer)
    p = np.asarray(point, dtype=float)
    return float(p @ np.cross(up, toward_viewer)), float(p @ up)


def _blocks(
    start: np.ndarray, direction: np.ndarray, low: np.ndarray, high: np.ndarray
) -> bool:
    """Whether the ray from ``start`` along ``direction`` passes through the
    inside of the box ``low``..``high``."""
    near, far = 0.0, np.inf
    for axis in range(3):
        if abs(direction[axis]) < 1e-12:
            inside = (
                low[axis] + _TOLERANCE_MM < start[axis] < high[axis] - _TOLERANCE_MM
            )
            if not inside:
                return False
            continue
        t1 = (low[axis] - start[axis]) / direction[axis]
        t2 = (high[axis] - start[axis]) / direction[axis]
        near, far = max(near, min(t1, t2)), min(far, max(t1, t2))
    return far - near > _TOLERANCE_MM


def visible_labels(assembly: Assembly, view: View) -> list[Label]:
    """Labels at the centers the viewer can see: no other piece lies between
    a piece's center and the viewer. In model order."""
    boxes = {}
    for piece_id, piece in assembly.model.pieces.items():
        low, high = assembly.placement.poses[piece_id].bounds(piece)
        boxes[piece_id] = (
            np.array([low.x, low.y, low.z]),
            np.array([high.x, high.y, high.z]),
        )
    toward_viewer = _unit(view.origin)
    labels = []
    for piece_id, (low, high) in boxes.items():
        center = (low + high) / 2
        hidden = any(
            _blocks(center, toward_viewer, *box)
            for other, box in boxes.items()
            if other != piece_id
        )
        if not hidden:
            labels.append(Label(piece_id, *project(view, center)))
    return labels
