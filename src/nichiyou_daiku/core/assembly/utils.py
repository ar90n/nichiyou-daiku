"""Utility functions for assembly operations.

This module provides helper functions for creating pilot holes
and generating joint IDs.
"""

from collections.abc import Callable

from ..geometry import Box, Point3D
from .models import Hole, Joint


def _create_pilot_hole_on_joint(
    box: Box,
    joint: Joint,
) -> tuple[Point3D, Hole]:
    """Create a pilot hole at the joint position.

    Args:
        box: Box of the piece
        joint: Joint where the hole is to be created

    Returns:
        Tuple of (3D position of hole, Hole specification)
    """
    point_3d = Point3D.of(box, joint.position)
    hole = Hole(diameter=3.0, depth=5.0)
    return (point_3d, hole)


def _create_joint_id_generator(piece_ids: list[str]) -> Callable[[str], str]:
    """Create a joint ID generator function with encapsulated state.

    Returns a closure that generates sequential joint IDs for each piece.
    The counter state is encapsulated within the closure.

    Args:
        piece_ids: List of piece IDs to initialize counters for

    Returns:
        A function that generates the next joint ID for a given piece_id

    Example:
        >>> generate_id = _create_joint_id_generator(["p1", "p2"])
        >>> generate_id("p1")
        'p1_j0'
        >>> generate_id("p1")
        'p1_j1'
        >>> generate_id("p2")
        'p2_j0'
    """
    counters: dict[str, int] = {piece_id: 0 for piece_id in piece_ids}

    def generate_next(piece_id: str) -> str:
        joint_id = f"{piece_id}_j{counters[piece_id]}"
        counters[piece_id] += 1
        return joint_id

    return generate_next
