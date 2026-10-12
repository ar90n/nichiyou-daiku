"""Export nichiyou-daiku assemblies to build123d format for 3D visualization.

This module renders an Assembly with build123d: each piece becomes a solid
(filleted, with its pilot holes) placed where the assembly's placement puts it.
"""

from typing import TYPE_CHECKING

import numpy as np

from nichiyou_daiku.core.assembly import (
    Assembly,
    Hole as NichiyouHole,
)
from nichiyou_daiku.core.geometry import (
    Point3D,
    SurfacePoint,
    Box as NichiyouBox,
)
from nichiyou_daiku.core.placement import Pose

# Check if build123d is available
HAS_BUILD123D = False
try:
    from build123d import (
        Box,
        Compound,
        Part,
        Location,
        Plane,
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
        Box,
        Compound,
        Part,
        Location,
        Plane,
        Align,
        fillet,
        Axis,
        Cylinder,
    )


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


def _location_of(pose: Pose) -> "Location":
    rotation = np.array(pose.rotation, dtype=float)
    return Location(
        Plane(
            origin=pose.translation,
            x_dir=tuple(rotation[:, 0]),
            z_dir=tuple(rotation[:, 2]),
        )
    )


def assembly_to_build123d(
    assembly: Assembly,
    fillet_radius: float = 5.0,
) -> "Compound":
    """Convert a nichiyou Assembly to a build123d Compound.

    Creates a build123d Part for each piece and places it where the
    assembly's placement puts it.

    Args:
        assembly: The nichiyou Assembly to convert
        fillet_radius: Radius for edge fillets in mm (default: 5.0, use 0 to disable)

    Returns:
        A build123d Compound containing all placed parts

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
            "Please install the viz extra, e.g. "
            'uv add "nichiyou-daiku[viz] @ git+https://github.com/ar90n/nichiyou-daiku"'
        )

    parts = []
    for piece_id, box in assembly.boxes.items():
        part = _create_piece_from(
            piece_id,
            box,
            fillet_radius,
            pilot_holes=assembly.pilot_holes.get(piece_id),
        )
        parts.append(part.locate(_location_of(assembly.placement.poses[piece_id])))

    return Compound(label=assembly.label or "assembly", children=parts)
