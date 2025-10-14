"""Export nichiyou-daiku assemblies to build123d format for 3D visualization.

This module provides conversion functions from our internal Assembly
representation to build123d objects that can be visualized in CAD tools.
"""

import math
from collections import defaultdict, deque
from typing import TYPE_CHECKING

import numpy as np

from nichiyou_daiku.core.assembly import Assembly, Joint as NichiyouJoint
from nichiyou_daiku.core.geometry import (
    Orientation3D,
    Point3D,
    Box as NichiyouBox,
)

# Check if build123d is available
HAS_BUILD123D = False
try:
    from build123d import Box, RigidJoint, Compound, Part, Location, Align, fillet, Axis

    HAS_BUILD123D = True
except ImportError:
    pass

if TYPE_CHECKING:
    from build123d import Box, RigidJoint, Compound, Part, Location, Align, fillet, Axis


def _as_euler_angles(
    orientation: Orientation3D, *, flip_dir: bool = False
) -> tuple[float, float, float]:
    dir_vec = np.asarray(
        [orientation.direction.x, orientation.direction.y, orientation.direction.z],
        dtype=float,
    )

    up_vec = np.asarray(
        [orientation.up.x, orientation.up.y, orientation.up.z], dtype=float
    )

    if flip_dir:
        dir_vec = -dir_vec

    dir_vec /= np.linalg.norm(dir_vec)
    up_vec /= np.linalg.norm(up_vec)

    # Calculate orthonormal basis vectors
    right = np.cross(dir_vec, up_vec)
    right /= np.linalg.norm(right)

    up = np.cross(right, dir_vec)
    up /= np.linalg.norm(up)

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


def _create_piece_from(id: str, box: NichiyouBox, fillet_radius: float) -> "Part":
    """Create a build123d Part from a nichiyou Box.

    Args:
        id: The piece ID
        box: The nichiyou Box to convert
        fillet_radius: Radius for edge fillets in mm (default: 5.0)

    Returns:
        A build123d Part with filleted edges
    """
    piece = (
        Box(
            length=float(box.shape.length),
            width=float(box.shape.width),
            height=float(box.shape.height),
            align=Align.MIN,
        )
        + Part()
    )

    if 0 < fillet_radius:
        filleted = fillet(piece.edges().filter_by(Axis.X), radius=fillet_radius)
        # Wrap the filleted result in a Part if it's a Compound
        if hasattr(filleted, "wrapped") and hasattr(Part, "__call__"):
            piece = Part(filleted.wrapped)
        else:
            piece = filleted  # type: ignore

    piece.label = id
    return piece  # type: ignore


def _create_joint_from(
    joint: NichiyouJoint, label: str, to_part: "Part", flip_dir: bool = False
) -> "RigidJoint":
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
            _as_tuple(position), _as_euler_angles(orientation, flip_dir=flip_dir)
        ),
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
) -> "Compound":
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
        >>> assembly = Assembly(boxes={}, joints={}, label="example")
        >>> compound = assembly_to_build123d(assembly, fillet_radius=3.0)
    """
    if not HAS_BUILD123D:
        raise ImportError(
            "build123d is required for 3D visualization. "
            "Please install it with: pip install nichiyou-daiku[viz]"
        )
    parts = {}

    # Create parts for all pieces
    for piece_id, box in assembly.boxes.items():
        if piece_id not in parts:
            parts[piece_id] = _create_piece_from(piece_id, box, fillet_radius)

    # Build mapping from model connections to joint pairs
    # We need to match the order: model.connections gives us (lhs_piece_id, rhs_piece_id)
    # and assembly.joint_pairs gives us joint IDs in the same order
    joint_pair_to_pieces: dict[tuple[str, str], tuple[str, str]] = {}
    for i, ((lhs_piece_id, rhs_piece_id), _) in enumerate(assembly.model.connections.items()):
        if i < len(assembly.joint_pairs):
            lhs_joint_id, rhs_joint_id = assembly.joint_pairs[i]
            joint_pair_to_pieces[(lhs_joint_id, rhs_joint_id)] = (lhs_piece_id, rhs_piece_id)

    # Build graph and create joints on parts
    graph = defaultdict(set)
    for lhs_joint_id, rhs_joint_id in assembly.joint_pairs:
        piece_pair = joint_pair_to_pieces.get((lhs_joint_id, rhs_joint_id))
        if piece_pair is None:
            continue

        lhs_piece_id, rhs_piece_id = piece_pair

        graph[lhs_piece_id].add(rhs_piece_id)
        graph[rhs_piece_id].add(lhs_piece_id)

        # Create joints on parts
        lhs_joint = assembly.joints[lhs_joint_id]
        rhs_joint = assembly.joints[rhs_joint_id]

        _create_joint_from(
            lhs_joint,
            label=f"to_{rhs_joint_id}",
            to_part=parts[lhs_piece_id],
        )

        _create_joint_from(
            rhs_joint,
            label=f"to_{lhs_joint_id}",
            to_part=parts[rhs_piece_id],
        )

    # BFS traversal to connect joints
    visited = set()
    processed_edges = set()

    # Process each connected component
    for start_piece in assembly.boxes:
        if start_piece in visited:
            continue

        queue = deque([start_piece])
        visited.add(start_piece)

        while queue:
            current_piece_id = queue.popleft()

            # Process all joint pairs
            for lhs_joint_id, rhs_joint_id in assembly.joint_pairs:
                piece_pair = joint_pair_to_pieces.get((lhs_joint_id, rhs_joint_id))
                if piece_pair is None:
                    continue

                lhs_piece_id, rhs_piece_id = piece_pair
                edge_key = (lhs_joint_id, rhs_joint_id)

                # Skip if already processed
                if edge_key in processed_edges:
                    continue

                # Check if this edge involves the current piece
                if lhs_piece_id == current_piece_id or rhs_piece_id == current_piece_id:
                    processed_edges.add(edge_key)
                    processed_edges.add((rhs_joint_id, lhs_joint_id))

                    # Connect the joints
                    lhs_joint_obj = parts[lhs_piece_id].joints[f"to_{rhs_joint_id}"]
                    rhs_joint_obj = parts[rhs_piece_id].joints[f"to_{lhs_joint_id}"]
                    lhs_joint_obj.connect_to(rhs_joint_obj)

                    # Add unvisited piece to queue
                    if lhs_piece_id not in visited:
                        visited.add(lhs_piece_id)
                        queue.append(lhs_piece_id)
                    if rhs_piece_id not in visited:
                        visited.add(rhs_piece_id)
                        queue.append(rhs_piece_id)

    return Compound(label=assembly.label or "assembly", children=list(parts.values()))
