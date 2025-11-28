"""Assembly module for 3D visualization and construction.

This module converts the abstract model representation into concrete
3D assembly information with positions and orientations.

Public API:
    - Hole: Specification for pilot holes
    - Joint: A joint point with position and orientation
    - JointPair: A pair of joints connecting two pieces
    - Assembly: Complete 3D assembly with all joints
    - project_joint: Project joint between coordinate systems
"""

from .builder import Assembly
from .models import Hole, Joint, JointPair
from .projection import project_joint

__all__ = [
    "Hole",
    "Joint",
    "JointPair",
    "Assembly",
    "project_joint",
]
