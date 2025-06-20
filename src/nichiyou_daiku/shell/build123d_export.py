"""Export nichiyou-daiku assemblies to build123d format for 3D visualization.

This module provides conversion functions from our internal Assembly
representation to build123d objects that can be visualized in CAD tools.
"""

import math
from typing import TYPE_CHECKING

from nichiyou_daiku.core.assembly import Assembly

if TYPE_CHECKING:
    from build123d import Compound


def _direction_to_euler_angles(direction: tuple[float, float, float]) -> tuple[float, float, float]:
    """Convert a direction vector to Euler angles (in degrees).
    
    This converts a direction vector (which represents the Z-axis of a coordinate system)
    to Euler angles using ZYX intrinsic rotations. We assume no roll (rotation around
    the final Z-axis).
    
    Args:
        direction: Direction vector (x, y, z) - should be normalized
        
    Returns:
        Tuple of (rx, ry, rz) Euler angles in degrees
    """
    x, y, z = direction
    
    # Handle edge cases for vertical directions
    if abs(z) > 0.9999:
        # Pointing straight up or down
        if z > 0:
            return (0.0, 0.0, 0.0)  # No rotation needed for +Z
        else:
            return (180.0, 0.0, 0.0)  # Flip around X axis for -Z
    
    # Calculate rotation angles
    # First rotate around Y to get the direction in the XZ plane
    ry = math.degrees(math.atan2(x, z))
    
    # Then rotate around X to get the final direction
    horizontal_length = math.sqrt(x*x + z*z)
    rx = math.degrees(math.atan2(-y, horizontal_length))
    
    # No rotation around Z (no roll)
    rz = 0.0
    
    return (rx, ry, rz)


def assembly_to_build123d(assembly: Assembly) -> "Compound":
    """Convert nichiyou-daiku Assembly to build123d Compound for 3D visualization.
    
    This function takes an Assembly containing positioned boxes and connections,
    and creates a build123d Compound that can be visualized using tools like
    OCP CAD Viewer. It uses RigidJoints to properly position and orient the pieces.
    
    Args:
        assembly: The Assembly object containing all 3D information (boxes and connections)
        
    Returns:
        A build123d Compound object representing the complete assembly
        
    Examples:
        >>> from nichiyou_daiku.core.model import Model
        >>> from nichiyou_daiku.core.piece import Piece, PieceType
        >>> from nichiyou_daiku.core.connection import (
        ...     Connection as PieceConn, BasePosition, FromTopOffset, Anchor
        ... )
        >>> from nichiyou_daiku.core.geometry import Edge, EdgePoint
        >>> # Create simple model
        >>> p1 = Piece.of(PieceType.PT_2x4, 1000.0, "p1")
        >>> p2 = Piece.of(PieceType.PT_2x4, 800.0, "p2")
        >>> conn = PieceConn.of(
        ...     base=BasePosition(face="top", offset=FromTopOffset(value=100)),
        ...     target=Anchor(
        ...         face="bottom",
        ...         edge_point=EdgePoint(edge=Edge(lhs="bottom", rhs="front"), value=50)
        ...     )
        ... )
        >>> model = Model.of(pieces=[p1, p2], connections=[])
        >>> assembly = Assembly.of(model)
        >>> # Convert to build123d
        >>> compound = assembly_to_build123d(assembly)  # doctest: +SKIP
        >>> # Can now visualize with: show(compound)
    """
    try:
        from build123d import Box as B3dBox, RigidJoint, Compound, Part, Location, Align
    except ImportError:
        raise ImportError(
            "build123d is required for 3D export. Install with: pip install build123d"
        )
    
    parts_map = {}
    for piece_id, box in assembly.boxes.items():
        b3d_box = B3dBox(
            length=float(box.shape.length),
            width=float(box.shape.width),
            height=float(box.shape.height),
            align=Align.MIN
        )
        parts_map[piece_id] = Part(b3d_box.wrapped)
    
    for (base_id, target_id), connection in assembly.connections.items():
        base_joint = connection.joint1
        target_joint = connection.joint2
        
        # Convert direction vectors to Euler angles
        base_angles = _direction_to_euler_angles((
            base_joint.direction.x,
            base_joint.direction.y,
            base_joint.direction.z
        ))
        
        target_angles = _direction_to_euler_angles((
            -target_joint.direction.x,
            -target_joint.direction.y,
            -target_joint.direction.z
        ))
        
        base_rigid_joint = RigidJoint(
            label=f"{base_id}_to_{target_id}",
            to_part=parts_map[base_id],
            joint_location=Location(
                (
                    base_joint.position.x,
                    base_joint.position.y,
                    base_joint.position.z
                ),
                base_angles
            )
        )

        target_rigid_joint = RigidJoint(
            label=f"{target_id}_to_{base_id}",
            to_part=parts_map[target_id],
            joint_location=Location(
                (
                    target_joint.position.x,
                    target_joint.position.y,
                    target_joint.position.z
                ),
                target_angles
            )
        )
        base_rigid_joint.connect_to(target_rigid_joint)
    
    return Compound(list(parts_map.values()))