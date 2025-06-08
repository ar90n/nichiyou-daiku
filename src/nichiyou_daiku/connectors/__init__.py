"""Connector system for joining lumber pieces.

This module provides edge-based connectors for joining lumber.
Currently supports aligned wood screw connections.
"""

from nichiyou_daiku.connectors.aligned_screw import AlignedScrewJoint

__all__ = [
    "AlignedScrewJoint",
]
