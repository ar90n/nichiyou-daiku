"""Shared utilities for shell module."""

from nichiyou_daiku.core.geometry import Point3D, Box, Face


def detect_face_from_point(point: Point3D, box: Box) -> Face:
    """Detect which face of the box a point lies on.

    Args:
        point: The 3D point to check
        box: The box to check against

    Returns:
        The face that the point lies on

    Raises:
        ValueError: If the point is not on any face of the box
    """
    tolerance = 0.001
    if abs(point.z - box.shape.length) < tolerance:
        return "top"
    if abs(point.z) < tolerance:
        return "down"
    if abs(point.x) < tolerance:
        return "left"
    if abs(point.x - box.shape.width) < tolerance:
        return "right"
    if abs(point.y - box.shape.height) < tolerance:
        return "front"
    if abs(point.y) < tolerance:
        return "back"
    raise ValueError(f"Point {point} is not on any face of box")
