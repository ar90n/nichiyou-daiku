"""Assembly module for 3D visualization and construction.

This module converts the abstract model representation into concrete
3D assembly information with positions and orientations.

Public API:
    - Hole: Specification for pilot holes
    - Assembly: Complete 3D assembly with placement, fasteners and pilot holes
    - Fastener / LayoutIssue / layout_fasteners: Dowels and screws in the contact area
"""

from .builder import Assembly
from .fasteners import layout_fasteners
from .models import Fastener, FastenerKind, Hole, LayoutIssue

__all__ = [
    "Hole",
    "Assembly",
    "Fastener",
    "FastenerKind",
    "LayoutIssue",
    "layout_fasteners",
]
