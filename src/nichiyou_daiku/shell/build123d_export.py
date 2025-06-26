"""Export nichiyou-daiku assemblies to build123d format for 3D visualization.

This module provides conversion functions from our internal Assembly
representation to build123d objects that can be visualized in CAD tools.
"""

import math
from collections import defaultdict, deque
from typing import Optional, TYPE_CHECKING

import numpy as np

# Lazy import handling for optional dependency
_BUILD123D_AVAILABLE = False
_BUILD123D_ERROR = None

try:
    from build123d import Box, RigidJoint, Compound, Part, Location, Align, fillet, Axis
    _BUILD123D_AVAILABLE = True
except ImportError as e:
    _BUILD123D_ERROR = e
    # Create placeholder types for type checking
    if TYPE_CHECKING:
        from build123d import Box, RigidJoint, Compound, Part, Location, Align, fillet, Axis

from nichiyou_daiku.core.assembly import Assembly, Joint as NichiyouJoint
from nichiyou_daiku.core.geometry import Orientation3D, Vector3D, Point3D, Box as NichiyouBox

def _as_euler_angles(orientation: Orientation3D, *, flip_dir: bool = False) -> tuple[float, float, float]:
    dir_vec = np.asarray([orientation.direction.x,
                          orientation.direction.y,
                          orientation.direction.z], dtype=float)

    up_vec  = np.asarray([orientation.up.x,
                          orientation.up.y,
                          orientation.up.z], dtype=float)

    if flip_dir:
        dir_vec = -dir_vec

    dir_vec /= np.linalg.norm(dir_vec)
    up_vec  /= np.linalg.norm(up_vec)

    # Calculate orthonormal basis vectors
    right = np.cross(dir_vec, up_vec)
    right /= np.linalg.norm(right)

    up = np.cross(right, dir_vec)
    up  /= np.linalg.norm(up)

    # Create rotation matrix
    R = np.column_stack((right, up, -dir_vec))

    # Extract Euler angles from rotation matrix
    sy = R[0, 2]
    if abs(sy) < 0.999999:
        ry = math.asin(sy)
        rx = math.atan2(-R[1, 2], R[2, 2])
        rz = math.atan2(-R[0, 1], R[0, 0])
    else:  # gimbal‑lock
        ry = math.copysign(math.pi / 2, sy)
        rx = math.atan2(math.copysign(1.0, sy) * R[1, 0], R[1, 1])
        rz = 0.0

    # Convert radians to degrees
    angles = np.degrees([rx, ry, rz])
    angles[np.isclose(angles, 0.0, atol=1e-10)] = 0.0
    return tuple(angles)


def _as_tuple(point: Point3D) -> tuple[float, float, float]:
    """Convert a Point3D to a tuple of floats.
    
    Args:
        point: The point to convert
        
    Returns:
        Tuple of (x, y, z) coordinates as floats
    """
    return (float(point.x), float(point.y), float(point.z))

def _create_piece_from(id: str, box: NichiyouBox, fillet_radius: float) -> 'Part':
    """Create a build123d Part from a nichiyou Box.
    
    Args:
        id: The piece ID
        box: The nichiyou Box to convert
        fillet_radius: Radius for edge fillets in mm (default: 5.0)
        
    Returns:
        A build123d Part with filleted edges
    """
    piece = Box(
        length=float(box.shape.length),
        width=float(box.shape.width),
        height=float(box.shape.height),
        align=Align.MIN,
    ) + Part()
    
    if 0 < fillet_radius:
        piece = fillet(piece.edges().filter_by(Axis.X), radius=fillet_radius)
    
    piece.label = id
    return piece


def _create_joint_from(joint: NichiyouJoint, label: str, to_part: 'Part', flip_dir: bool = False) -> 'RigidJoint':
    """Create a build123d RigidJoint from a nichiyou Joint.
    
    Args:
        joint: The nichiyou Joint to convert
        label: Label for the rigid joint
        to_part: The Part this joint belongs to
        flip_dir: Whether to flip the direction vector (for target joints)
        
    Returns:
        A build123d RigidJoint
    """
    orientation = joint.orientation
    position = joint.position

    return RigidJoint(
        label=label,
        to_part=to_part,
        joint_location=Location(
            _as_tuple(position),
            _as_euler_angles(orientation, flip_dir=flip_dir)
        )
    )

def _connect(parts, src_id: str, dst_id: str):
    """Connect two parts using their rigid joints.
    
    Args:
        parts: Dictionary mapping part IDs to Part objects
        src_id: Source part ID
        dst_id: Destination part ID
    """
    src_joint = parts[src_id].joints[f"to_{dst_id}"]
    dst_joint = parts[dst_id].joints[f"to_{src_id}"]
    src_joint.connect_to(dst_joint)

def assembly_to_build123d(
    assembly: Assembly, 
    fillet_radius: float = 5.0,
) -> 'Compound':
    """Convert a nichiyou Assembly to a build123d Compound.
    
    Creates build123d Parts for each piece in the assembly and connects them
    using RigidJoints based on the assembly's connection information.
    
    Args:
        assembly: The nichiyou Assembly to convert
        fillet_radius: Radius for edge fillets in mm (default: 5.0, use 0 to disable)
        
    Returns:
        A build123d Compound containing all connected parts
        
    Raises:
        ImportError: If build123d is not installed
        
    Example:
        >>> from nichiyou_daiku.core.assembly import Assembly
        >>> assembly = Assembly(boxes={}, connections={})
        >>> compound = assembly_to_build123d(assembly, fillet_radius=3.0)
    """
    if not _BUILD123D_AVAILABLE:
        raise ImportError(
            "build123d is required for 3D visualization. "
            "Please install it with: pip install build123d"
        ) from _BUILD123D_ERROR
    parts = {}
    
    # Create parts for all pieces
    for piece_id, box in assembly.boxes.items():
        if piece_id not in parts:
            parts[piece_id] = _create_piece_from(piece_id, box, fillet_radius)
    
    # Build graph from connections
    graph = defaultdict(set)
    for (base_id, target_id),c in assembly.connections.items():
        graph[base_id].add(target_id)
        _create_joint_from(
            c.joint1,
            label=f"to_{target_id}",
            to_part=parts[base_id],
        )

        graph[target_id].add(base_id)
        _create_joint_from(
            c.joint2,
            label=f"to_{base_id}",
            to_part=parts[target_id],
            flip_dir=True
        )

    
    # BFS traversal
    visited = set()
    processed_edges = set()
    
    # Process each connected component
    for start_piece in assembly.boxes:
        if start_piece in visited:
            continue
            
        queue = deque([start_piece])
        visited.add(start_piece)

        while queue:
            current_id = queue.popleft()
            
            # Process all neighbors
            for neighbor_id in graph[current_id]:
                # Skip if this edge already processed
                if (current_id, neighbor_id) in processed_edges:
                    continue
                processed_edges.add((current_id, neighbor_id))
                processed_edges.add((neighbor_id, current_id))

                _connect(parts, current_id, neighbor_id)
                
                # Add neighbor to queue if not visited
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append(neighbor_id)

    return Compound(label=assembly.label, children=list(parts.values()))