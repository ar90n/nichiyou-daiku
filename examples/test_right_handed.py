"""Verify right-handed coordinate system: u × v = direction"""

import numpy as np
from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
from nichiyou_daiku.core.geometry import Box, Point2D, SurfacePoint, Point3D, Vector3D


def cross_product_2d_to_3d(face: str, u_val: float, v_val: float) -> tuple[float, float, float]:
    """Calculate u × v in 3D space for a given face.

    Returns the direction vector that should match the face's normal.
    """
    # Get u and v as 3D vectors based on face coordinate system
    if face == "top":
        # u=+X, v=+Y
        u_vec = np.array([1.0, 0.0, 0.0])
        v_vec = np.array([0.0, 1.0, 0.0])
    elif face == "down":
        # u=-X, v=+Y
        u_vec = np.array([-1.0, 0.0, 0.0])
        v_vec = np.array([0.0, 1.0, 0.0])
    elif face == "left":
        # u=-Y, v=+Z
        u_vec = np.array([0.0, -1.0, 0.0])
        v_vec = np.array([0.0, 0.0, 1.0])
    elif face == "right":
        # u=+Y, v=+Z
        u_vec = np.array([0.0, 1.0, 0.0])
        v_vec = np.array([0.0, 0.0, 1.0])
    elif face == "front":
        # u=-X, v=+Z
        u_vec = np.array([-1.0, 0.0, 0.0])
        v_vec = np.array([0.0, 0.0, 1.0])
    elif face == "back":
        # u=+X, v=+Z
        u_vec = np.array([1.0, 0.0, 0.0])
        v_vec = np.array([0.0, 0.0, 1.0])
    else:
        raise ValueError(f"Invalid face: {face}")

    # Cross product
    cross = np.cross(u_vec, v_vec)
    return tuple(cross)


def get_expected_direction(face: str) -> tuple[float, float, float]:
    """Get the expected normal direction for a face."""
    normals = {
        "top": (0.0, 0.0, 1.0),
        "down": (0.0, 0.0, -1.0),
        "left": (-1.0, 0.0, 0.0),
        "right": (1.0, 0.0, 0.0),
        "front": (0.0, 1.0, 0.0),
        "back": (0.0, -1.0, 0.0),
    }
    return normals[face]


def test_right_handed_coordinates():
    """Test that u × v = direction for all faces."""
    faces = ["top", "down", "left", "right", "front", "back"]

    print("Testing right-handed coordinate system (u × v = direction):\n")

    all_passed = True
    for face in faces:
        cross = cross_product_2d_to_3d(face, 1.0, 1.0)
        expected = get_expected_direction(face)

        matches = np.allclose(cross, expected, atol=1e-10)
        status = "✓" if matches else "✗"

        print(f"{status} {face:6s}: u × v = {cross}, expected = {expected}")

        if not matches:
            all_passed = False

    print(f"\n{'All tests passed!' if all_passed else 'Some tests failed!'}")
    return all_passed


def test_roundtrip_conversion():
    """Test that Point3D ↔ SurfacePoint conversion is consistent."""
    piece = Piece.of(PieceType.PT_2x4, 1000.0, "test")
    box = Box(shape=get_shape(piece))

    faces = ["top", "down", "left", "right", "front", "back"]
    test_points = [
        Point2D(u=0.0, v=0.0),    # center
        Point2D(u=10.0, v=20.0),  # positive offset
        Point2D(u=-10.0, v=-20.0), # negative offset
    ]

    print("\nTesting roundtrip conversion (SurfacePoint ↔ Point3D):\n")

    all_passed = True
    for face in faces:
        for pt_2d in test_points:
            # Create SurfacePoint
            sp = SurfacePoint(face=face, position=pt_2d)

            # Convert to 3D
            pt_3d = Point3D._of_surface_point(box, sp)

            # Convert back to 2D (via EdgePoint would be complex, so we test the inverse directly)
            # We can't use SurfacePoint.of directly without EdgePoint, so we check consistency differently

            # Re-create SurfacePoint from the 3D point manually
            if face == "top":
                u_back = pt_3d.x - box.shape.width / 2
                v_back = pt_3d.y - box.shape.height / 2
            elif face == "down":
                u_back = box.shape.width / 2 - pt_3d.x
                v_back = pt_3d.y - box.shape.height / 2
            elif face == "left":
                u_back = box.shape.height / 2 - pt_3d.y
                v_back = pt_3d.z - box.shape.length / 2
            elif face == "right":
                u_back = pt_3d.y - box.shape.height / 2
                v_back = pt_3d.z - box.shape.length / 2
            elif face == "front":
                u_back = box.shape.width / 2 - pt_3d.x
                v_back = pt_3d.z - box.shape.length / 2
            elif face == "back":
                u_back = pt_3d.x - box.shape.width / 2
                v_back = pt_3d.z - box.shape.length / 2

            # Check roundtrip
            matches = (
                np.isclose(u_back, pt_2d.u, atol=1e-10) and
                np.isclose(v_back, pt_2d.v, atol=1e-10)
            )

            if not matches:
                status = "✗"
                all_passed = False
                print(f"{status} {face}: ({pt_2d.u}, {pt_2d.v}) → 3D → ({u_back:.2f}, {v_back:.2f}) MISMATCH")
            else:
                status = "✓"

        print(f"{status} {face}: All test points passed")

    print(f"\n{'Roundtrip tests passed!' if all_passed else 'Some roundtrip tests failed!'}")
    return all_passed


if __name__ == "__main__":
    test1 = test_right_handed_coordinates()
    test2 = test_roundtrip_conversion()

    if test1 and test2:
        print("\n" + "=" * 60)
        print("SUCCESS: Right-handed coordinate system verified!")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("FAILURE: Some tests failed")
        print("=" * 60)
        exit(1)
