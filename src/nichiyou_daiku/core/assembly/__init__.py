"""Assembly module for 3D visualization and construction.

This module converts the abstract model representation into concrete
3D assembly information with positions and orientations.

Public API:
    - Hole: Specification for pilot holes
    - Joint: A joint point with position and orientation
    - JointPair: A pair of joints connecting two pieces
    - Assembly: Complete 3D assembly with all joints
    - find_joints_outside_pieces: Joints the dowel layout put beside their piece
    - project_joint: Project joint between coordinate systems
"""

from .builder import Assembly, find_joints_outside_pieces
from .models import Hole, Joint, JointPair
from .projection import project_joint

__all__ = [
    "Hole",
    "Joint",
    "JointPair",
    "Assembly",
    "find_joints_outside_pieces",
    "project_joint",
]
