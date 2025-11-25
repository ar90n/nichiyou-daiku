"""Assembly module for 3D visualization and construction.

This module converts the abstract model representation into concrete
3D assembly information with positions and orientations.

Public API:
    - Hole: Specification for pilot holes
    - Joint: A joint point with position and orientation
    - JointPair: A pair of joints connecting two pieces
    - Assembly: Complete 3D assembly with all joints

Internal functions (for testing):
    - _project_joint: Project joint between coordinate systems
    - _project_surface_point: Project surface point between coordinate systems
"""

from .builder import Assembly
from .models import Hole, Joint, JointPair
from .projection import _project_joint, _project_surface_point

__all__ = [
    # Public API
    "Hole",
    "Joint",
    "JointPair",
    "Assembly",
    # Internal functions (exported for testing)
    "_project_joint",
    "_project_surface_point",
]
