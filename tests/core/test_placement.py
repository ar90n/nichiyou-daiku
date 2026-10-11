"""Tests for solving piece placement from connections."""

import numpy as np
import pytest

from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.geometry import FromMin, Point3D, Vector3D, is_adjacent
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.placement import Pose, relative_rotation

FACES = ["top", "down", "left", "right", "front", "back"]
ADJACENT = [(c, e) for c in FACES for e in FACES if is_adjacent(c, e)]


def _vec(face) -> np.ndarray:
    v = Vector3D.normal_of(face)
    return np.array([v.x, v.y, v.z])


def _bound(piece: Piece, contact, edge) -> BoundAnchor:
    return BoundAnchor(
        piece=piece,
        anchor=Anchor(
            contact_face=contact, edge_shared_face=edge, offset=FromMin(value=0)
        ),
    )


class TestPose:
    def test_identity_pose_leaves_points_alone(self):
        point = Point3D(x=1.0, y=2.0, z=3.0)
        assert Pose().apply(point) == point

    def test_bounds_of_rotated_and_moved_piece(self):
        piece = Piece.of(PieceType.PT_2x4, 500.0, "p")
        # local (x, y, z) -> (-y, x, z), then +10 along X
        pose = Pose(
            rotation=((0, -1, 0), (1, 0, 0), (0, 0, 1)), translation=(10.0, 0.0, 0.0)
        )
        low, high = pose.bounds(piece)
        assert (low.x, low.y, low.z) == (-28.0, 0.0, 0.0)
        assert (high.x, high.y, high.z) == (10.0, 89.0, 500.0)


class TestRelativeRotation:
    @pytest.mark.parametrize("base_faces", ADJACENT)
    @pytest.mark.parametrize("target_faces", ADJACENT)
    def test_is_a_proper_signed_permutation(self, base_faces, target_faces):
        a = Piece.of(PieceType.PT_2x4, 500.0, "a")
        b = Piece.of(PieceType.PT_2x4, 300.0, "b")
        rotation = relative_rotation(_bound(a, *base_faces), _bound(b, *target_faces))
        assert rotation.dtype.kind == "i"
        assert set(np.abs(rotation).sum(axis=0)) == {1}
        assert set(np.abs(rotation).sum(axis=1)) == {1}
        assert round(np.linalg.det(rotation)) == 1

    @pytest.mark.parametrize("base_faces", ADJACENT)
    @pytest.mark.parametrize("target_faces", ADJACENT)
    def test_contact_faces_meet_and_edge_faces_are_flush(
        self, base_faces, target_faces
    ):
        a = Piece.of(PieceType.PT_2x4, 500.0, "a")
        b = Piece.of(PieceType.PT_2x4, 300.0, "b")
        rotation = relative_rotation(_bound(a, *base_faces), _bound(b, *target_faces))
        assert np.array_equal(rotation @ _vec(target_faces[0]), -_vec(base_faces[0]))
        assert np.array_equal(rotation @ _vec(target_faces[1]), _vec(base_faces[1]))
