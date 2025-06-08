"""Connector system for joining lumber pieces.

This module provides edge-based connectors for joining lumber.
Currently supports aligned wood screw connections.
"""

from nichiyou_daiku.connectors.aligned_screw import (
    AlignedScrewJoint,
    DrillPoint,
    EdgeAlignment,
    calculate_screw_positions,
    generate_drill_points,
    validate_edge_alignment,
)

__all__ = [
    "AlignedScrewJoint",
    "DrillPoint",
    "EdgeAlignment",
    "calculate_screw_positions",
    "generate_drill_points",
    "validate_edge_alignment",
]
