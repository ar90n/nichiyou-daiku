"""Export nichiyou-daiku assemblies to build123d format for 3D visualization.

This module provides conversion functions from our internal Assembly
representation to build123d objects that can be visualized in CAD tools.
"""

import math
from collections import deque
from typing import TYPE_CHECKING

import numpy as np

from nichiyou_daiku.core.assembly import Assembly, Joint as NichiyouJoint, Hole as NichiyouHole
from nichiyou_daiku.core.geometry import (
    Orientation3D,
    Point3D,
    Box as NichiyouBox,
    Face,
)

# Check if build123d is available
HAS_BUILD123D = False
try:
    from build123d import Box, RigidJoint, Compound, Part, Location, Align, fillet, Axis, Cylinder

    HAS_BUILD123D = True
except ImportError:
    pass

if TYPE_CHECKING:
    from build123d import Box, RigidJoint, Compound, Part, Location, Align, fillet, Axis, Cylinder


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


def _detect_face_from_point(point: Point3D, box: NichiyouBox) -> Face:
    """Detect which face of the box a point lies on.

    Args:
        point: The 3D point to check
        box: The box to check against

    Returns:
        The face that the point lies on

    Raises:
        ValueError: If the point is not on any face of the box
    """
    tolerance = 0.001
    if abs(point.z - box.shape.length) < tolerance:
        return "top"
    if abs(point.z) < tolerance:
        return "down"
    if abs(point.x) < tolerance:
        return "left"
    if abs(point.x - box.shape.width) < tolerance:
        return "right"
    if abs(point.y - box.shape.height) < tolerance:
        return "front"
    if abs(point.y) < tolerance:
        return "back"
    raise ValueError(f"Point {point} is not on any face of box")


def _create_hole(
    point: Point3D,
    hole: NichiyouHole,
    box: NichiyouBox,
) -> "Part":
    """Create a cylinder for hole subtraction at the specified position.

    Args:
        point: The 3D position of the hole center on the box surface
        hole: The hole specification (diameter and depth)
        box: The box containing dimension information

    Returns:
        A build123d Part (cylinder) positioned and oriented for subtraction
    """
    face = _detect_face_from_point(point, box)

    # Face rotation angles to orient cylinder inward (Z-axis aligned with hole direction)
    face_rotations: dict[Face, tuple[float, float, float]] = {
        "left": (0, 90, 0),     # cylinder Z -> +X (inward)
        "right": (0, -90, 0),   # cylinder Z -> -X (inward)
        "back": (-90, 0, 0),    # cylinder Z -> +Y (inward)
        "front": (90, 0, 0),    # cylinder Z -> -Y (inward)
        "down": (0, 0, 0),      # cylinder Z -> +Z (inward)
        "top": (180, 0, 0),     # cylinder Z -> -Z (inward)
    }

    # Calculate depth: use specified depth or fixed value for through-holes
    depth = hole.depth if hole.depth is not None else 100.0

    # Create cylinder centered at origin, then rotate and translate
    cylinder = Cylinder(
        radius=hole.diameter / 2,
        height=depth,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )

    rotation = face_rotations[face]
    position = _as_tuple(point)

    return cylinder.locate(Location(position, rotation))


def _create_piece_from(
    id: str,
    box: NichiyouBox,
    fillet_radius: float,
    pilot_holes: list[tuple[Point3D, NichiyouHole]] | None = None,
) -> "Part":
    """Create a build123d Part from a nichiyou Box.

    Args:
        id: The piece ID
        box: The nichiyou Box to convert
        fillet_radius: Radius for edge fillets in mm (default: 5.0)
        pilot_holes: List of (position, hole) tuples for pilot holes

    Returns:
        A build123d Part with filleted edges and pilot holes
    """
    piece = (
        Box(
            length=float(box.shape.width),
            width=float(box.shape.height),
            height=float(box.shape.length),
            align=Align.MIN,
        )
        + Part()
    )

    # Apply fillet first
    if 0 < fillet_radius:
        filleted = fillet(piece.edges().filter_by(Axis.X), radius=fillet_radius)
        # Wrap the filleted result in a Part if it's a Compound
        if hasattr(filleted, "wrapped") and hasattr(Part, "__call__"):
            piece = Part(filleted.wrapped)
        else:
            piece = filleted  # type: ignore

    # Subtract pilot holes after fillet
    if pilot_holes:
        for point, hole in pilot_holes:
            hole_cylinder = _create_hole(point, hole, box)
            piece = piece - hole_cylinder

    piece.label = id
    return piece  # type: ignore


def _create_joint_from(
    joint: NichiyouJoint, box: NichiyouBox, label: str, to_part: "Part", flip_dir: bool = False
) -> "RigidJoint":
    """Create a build123d RigidJoint from a nichiyou Joint.

    Args:
        joint: The nichiyou Joint to convert
        box: The box for converting SurfacePoint to Point3D
        label: Label for the rigid joint
        to_part: The Part this joint belongs to
        flip_dir: Whether to flip the direction vector (for target joints)

    Returns:
        A build123d RigidJoint
    """
    orientation = joint.orientation
    # Convert SurfacePoint to Point3D using the box
    position = Point3D.of(box, joint.position)

    return RigidJoint(
        label=label,
        to_part=to_part,
        joint_location=Location(
            _as_tuple(position), _as_euler_angles(orientation, flip_dir=flip_dir)
        ),
    )


def _connect(parts, src_joint_id: str, dst_joint_id: str):
    """Connect two parts using their rigid joints.

    Args:
        parts: Dictionary mapping part IDs to Part objects
        src_joint_id: Source joint ID (e.g., "p1_j0")
        dst_joint_id: Destination joint ID (e.g., "p2_j0")
    """
    src_id = src_joint_id.rsplit("_j", 1)[0]
    dst_id = dst_joint_id.rsplit("_j", 1)[0]
    src_joint = parts[src_id].joints.get(f"to_{dst_id}")
    dst_joint = parts[dst_id].joints.get(f"to_{src_id}")
    if src_joint and dst_joint:
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
            parts[piece_id] = _create_piece_from(
                piece_id,
                box,
                fillet_radius,
                pilot_holes=assembly.pilot_holes.get(piece_id),
            )

    # Build graph from connections
    joints = {}
    for lhs_joint_id, rhs_joint_id in assembly.joint_conns:
        lhs_joint = assembly.joints[lhs_joint_id]
        rhs_joint = assembly.joints[rhs_joint_id]

        # Extract piece IDs from joint IDs
        lhs_id = lhs_joint_id.rsplit("_j", 1)[0]
        rhs_id = rhs_joint_id.rsplit("_j", 1)[0]

        joints.setdefault(lhs_id, []).append((lhs_joint_id, rhs_joint_id))
        _create_joint_from(
            lhs_joint,
            assembly.boxes[lhs_id],
            label=f"to_{rhs_id}",
            to_part=parts[lhs_id],
        )
        joints.setdefault(rhs_id, []).append((rhs_joint_id, lhs_joint_id))
        _create_joint_from(
            rhs_joint,
            assembly.boxes[rhs_id],
            label=f"to_{lhs_id}",
            to_part=parts[rhs_id],
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
            current_piece_id = queue.popleft()

            # Process all neighbors
            for current_id, neighbor_id in joints.get(current_piece_id, []):
                if (current_id, neighbor_id) in processed_edges:
                    continue
                if (neighbor_id, current_id) in processed_edges:
                    continue
                processed_edges.add((current_id, neighbor_id))
                processed_edges.add((neighbor_id, current_id))

                _connect(parts, current_id, neighbor_id)

                # Add neighbor to queue if not visited
                neighbor_piece_id = neighbor_id.rsplit("_j", 1)[0]
                if neighbor_piece_id not in visited:
                    visited.add(neighbor_piece_id)
                    queue.append(neighbor_piece_id)

    return Compound(label=assembly.label or "assembly", children=list(parts.values()))
