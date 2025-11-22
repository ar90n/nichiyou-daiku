"""Geometric types for woodworking dimensions and coordinates.

This module re-exports all geometric types from their respective modules
for convenience.
"""

# Re-export all types from submodules
from .dimensions import Millimeters, Shape2D, Shape3D
from .box import Box
from .face import (
    Face,
    opposite,
    cross,
    is_same_axis,
    is_adjacent,
    is_down_to_top_axis,
    is_left_to_right_axis,
    is_back_to_front_axis,
    is_positive,
)
from .edge import Edge, EdgePoint
from .corner import Corner
from .coordinates import Point2D, Point3D, Vector3D, Orientation3D, Orientation, SurfacePoint
from .offset import Offset, FromMax, FromMin

# Explicitly define what's exported when using "from geometry import *"
__all__ = [
    # From dimensions
    "Millimeters",
    "Shape2D",
    "Shape3D",
    # From box
    "Box",
    # From face
    "Face",
    "opposite",
    "cross",
    "is_same_axis",
    "is_adjacent",
    "is_down_to_top_axis",
    "is_left_to_right_axis",
    "is_back_to_front_axis",
    "is_positive",
    # From edge
    "Edge",
    "EdgePoint",
    # From corner
    "Corner",
    # From coordinates
    "Point2D",
    "Point3D",
    "Vector3D",
    "Orientation",
    "Orientation3D",
    "SurfacePoint",
    # From offset
    "Offset",
    "FromMin",
    "FromMax",
]
