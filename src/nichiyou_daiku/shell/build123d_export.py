"""Export nichiyou-daiku assemblies to build123d format for 3D visualization.

This module provides conversion functions from our internal Assembly
representation to build123d objects that can be visualized in CAD tools.
"""

import math
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from nichiyou_daiku.core.assembly import (
    Assembly,
    Joint as NichiyouJoint,
    Hole as NichiyouHole,
)
from nichiyou_daiku.core.geometry import (
    Orientation3D,
    Point3D,
    SurfacePoint,
    Box as NichiyouBox,
)

# Check if build123d is available
HAS_BUILD123D = False
try:
    from build123d import (
        Box,
        RigidJoint,
        Compound,
        Part,
        Location,
        Align,
        fillet,
        Axis,
        Cylinder,
    )

    HAS_BUILD123D = True
except ImportError:
    pass

if TYPE_CHECKING:
    from build123d import (
        BoundBox,
        Box,
        RigidJoint,
        Compound,
        Part,
        Location,
        Align,
        fillet,
        Axis,
        Cylinder,
    )


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


def _create_hole(
    position: SurfacePoint,
    hole: NichiyouHole,
    box: NichiyouBox,
) -> "Part":
    """Create a cylinder for hole subtraction at the specified position.

    Args:
        position: The hole center on the face it is drilled into
        hole: The hole specification (diameter and depth)
        box: The box containing dimension information

    Returns:
        A build123d Part (cylinder) positioned and oriented for subtraction
    """
    face = position.face
    point = Point3D.of(box, position)

    # Face rotation angles to orient cylinder inward (Z-axis aligned with hole direction)
    face_rotations: dict[str, tuple[float, float, float]] = {
        "left": (0, 90, 0),  # cylinder Z -> +X (inward)
        "right": (0, -90, 0),  # cylinder Z -> -X (inward)
        "back": (-90, 0, 0),  # cylinder Z -> +Y (inward)
        "front": (90, 0, 0),  # cylinder Z -> -Y (inward)
        "down": (0, 0, 0),  # cylinder Z -> +Z (inward)
        "top": (180, 0, 0),  # cylinder Z -> -Z (inward)
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
    return cylinder.locate(Location(_as_tuple(point), rotation))


def _create_piece_from(
    id: str,
    box: NichiyouBox,
    fillet_radius: float,
    pilot_holes: list[tuple[SurfacePoint, NichiyouHole]] | None = None,
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

    # Round the four long edges (the piece's length runs along Z). Two fillets
    # meeting across the thickness would fail, so keep the radius below half
    # of the smaller cross-section side.
    radius = min(fillet_radius, min(box.shape.width, box.shape.height) / 2 * 0.99)
    if 0 < radius:
        piece = Part(fillet(piece.edges().filter_by(Axis.Z), radius=radius).wrapped)

    # Subtract pilot holes after fillet
    if pilot_holes:
        for position, hole in pilot_holes:
            hole_cylinder = _create_hole(position, hole, box)
            piece = piece - hole_cylinder

    piece.label = id
    return piece  # type: ignore


def _create_joint_from(
    joint: NichiyouJoint,
    box: NichiyouBox,
    label: str,
    to_part: "Part",
    flip_dir: bool = False,
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
    parts[src_id].joints[src_joint_id].connect_to(parts[dst_id].joints[dst_joint_id])


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
        >>> from nichiyou_daiku.core.model import Model
        >>> from nichiyou_daiku.core.assembly import Assembly
        >>> model = Model.of(pieces=[], connections=[])
        >>> assembly = Assembly.of(model)
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
            label=lhs_joint_id,
            to_part=parts[lhs_id],
        )
        joints.setdefault(rhs_id, []).append((rhs_joint_id, lhs_joint_id))
        _create_joint_from(
            rhs_joint,
            assembly.boxes[rhs_id],
            label=rhs_joint_id,
            to_part=parts[rhs_id],
            flip_dir=True,
        )

    # BFS traversal: each piece is placed once, by the first joint that
    # reaches it. Joints that close a loop are left as they are; use
    # find_joint_mismatches() to see whether they agree with the placement.
    visited = set()

    # Process each connected component
    for start_piece in assembly.boxes:
        if start_piece in visited:
            continue

        queue = deque([start_piece])
        visited.add(start_piece)

        while queue:
            current_piece_id = queue.popleft()

            for current_id, neighbor_id in joints.get(current_piece_id, []):
                neighbor_piece_id = neighbor_id.rsplit("_j", 1)[0]
                if neighbor_piece_id in visited:
                    continue
                _connect(parts, current_id, neighbor_id)
                visited.add(neighbor_piece_id)
                queue.append(neighbor_piece_id)

    return Compound(label=assembly.label or "assembly", children=list(parts.values()))


@dataclass
class OverlapResult:
    """Result of overlap detection between pieces.

    Attributes:
        has_overlap: True if any pieces overlap
        overlapping_pairs: List of (label1, label2) tuples for overlapping pieces
        volume: Total interference volume in mm³
    """

    has_overlap: bool
    overlapping_pairs: list[tuple[str, str]]
    volume: float


def check_overlap(compound: "Compound", tolerance: float = 1e-5) -> OverlapResult:
    """Detect overlapping pieces in a Compound.

    Intersects every pair of children whose bounding boxes overlap and
    reports each pair whose common volume exceeds ``tolerance``.

    Args:
        compound: The Compound from assembly_to_build123d()
        tolerance: Minimum common volume in mm³ that counts as an overlap

    Returns:
        OverlapResult with detection results

    Raises:
        ImportError: If build123d is not installed

    Example:
        >>> from nichiyou_daiku.core.model import Model
        >>> from nichiyou_daiku.core.assembly import Assembly
        >>> model = Model.of(pieces=[], connections=[])
        >>> assembly = Assembly.of(model)
        >>> compound = assembly_to_build123d(assembly)
        >>> result = check_overlap(compound)
        >>> result.has_overlap
        False
    """
    if not HAS_BUILD123D:
        raise ImportError(
            "build123d is required for overlap detection. "
            "Please install it with: pip install nichiyou-daiku[viz]"
        )

    children = list(compound.children)
    pairs: list[tuple[str, str]] = []
    total_volume = 0.0
    for i, lhs in enumerate(children):
        lhs_bbox = lhs.bounding_box()
        for rhs in children[i + 1 :]:
            if not _bounding_boxes_overlap(lhs_bbox, rhs.bounding_box()):
                continue
            volume = _common_volume(lhs, rhs)
            if volume > tolerance:
                pairs.append((lhs.label or "?", rhs.label or "?"))
                total_volume += volume

    return OverlapResult(
        has_overlap=bool(pairs), overlapping_pairs=pairs, volume=total_volume
    )


def _common_volume(lhs: "Part", rhs: "Part") -> float:
    # Intersect the bare solids: Part.intersect re-parents the part's joints
    # onto the result, which would corrupt later joint checks.
    volume = 0.0
    for lhs_solid in lhs.solids():
        for rhs_solid in rhs.solids():
            common = lhs_solid.intersect(rhs_solid)
            if common is not None:
                volume += sum(solid.volume for solid in common.solids())
    return volume


def _bounding_boxes_overlap(lhs: "BoundBox", rhs: "BoundBox") -> bool:
    return (
        lhs.min.X < rhs.max.X
        and rhs.min.X < lhs.max.X
        and lhs.min.Y < rhs.max.Y
        and rhs.min.Y < lhs.max.Y
        and lhs.min.Z < rhs.max.Z
        and rhs.min.Z < lhs.max.Z
    )


def find_joint_mismatches(
    assembly: Assembly, compound: "Compound", tolerance: float = 0.01
) -> list[tuple[str, str, float]]:
    """Find connected joints that do not meet after placement.

    Each piece is placed by the first joint that reaches it, so a connection
    that contradicts the others ends up with its two joints apart.

    Args:
        assembly: The Assembly the compound was built from
        compound: The Compound from assembly_to_build123d()
        tolerance: Maximum distance in mm between joints that still counts as met

    Returns:
        (joint_id, joint_id, distance in mm) for every pair further apart than
        ``tolerance``
    """
    parts = {child.label: child for child in compound.children}
    mismatches = []
    for lhs_joint_id, rhs_joint_id in assembly.joint_conns:
        lhs_part = parts[lhs_joint_id.rsplit("_j", 1)[0]]
        rhs_part = parts[rhs_joint_id.rsplit("_j", 1)[0]]
        lhs_position = lhs_part.joints[lhs_joint_id].location.position
        rhs_position = rhs_part.joints[rhs_joint_id].location.position
        distance = (lhs_position - rhs_position).length
        if distance > tolerance:
            mismatches.append((lhs_joint_id, rhs_joint_id, distance))
    return mismatches
