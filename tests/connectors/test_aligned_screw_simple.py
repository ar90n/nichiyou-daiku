"""Tests for simplified aligned wood screw connector."""

import pytest

from nichiyou_daiku.connectors.aligned_screw import AlignedScrewJoint
from nichiyou_daiku.core.lumber import Face
from nichiyou_daiku.core.geometry import EdgePoint


class TestAlignedScrewJoint:
    """Test the simplified AlignedScrewJoint class."""

    def test_joint_creation(self):
        """Test creating an aligned screw joint."""
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        assert joint.src_face == Face.TOP
        assert joint.dst_face == Face.TOP
        assert joint.src_edge_point.face1 == Face.TOP
        assert joint.src_edge_point.face2 == Face.RIGHT
        assert joint.src_edge_point.position == 0.5
        assert joint.dst_edge_point.face1 == Face.TOP
        assert joint.dst_edge_point.face2 == Face.LEFT
        assert joint.dst_edge_point.position == 0.5

    def test_joint_immutability(self):
        """Test that joint is immutable."""
        joint = AlignedScrewJoint(
            src_face=Face.FRONT,
            dst_face=Face.BACK,
            src_edge_point=EdgePoint(Face.FRONT, Face.TOP, 0.0),
            dst_edge_point=EdgePoint(Face.BACK, Face.TOP, 0.0),
        )

        with pytest.raises(AttributeError):
            joint.src_face = Face.LEFT

        with pytest.raises(AttributeError):
            joint.src_edge_point = EdgePoint(Face.FRONT, Face.BOTTOM, 0.5)

    def test_joint_equality(self):
        """Test joint equality comparison."""
        edge1 = EdgePoint(Face.TOP, Face.RIGHT, 0.25)
        edge2 = EdgePoint(Face.TOP, Face.LEFT, 0.25)

        joint1 = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=edge1,
            dst_edge_point=edge2,
        )

        joint2 = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=edge1,
            dst_edge_point=edge2,
        )

        joint3 = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.BOTTOM,  # Different face
            src_edge_point=edge1,
            dst_edge_point=edge2,
        )

        assert joint1 == joint2
        assert joint1 != joint3

    def test_various_edge_connections(self):
        """Test different valid edge connection scenarios."""
        # TOP-RIGHT to TOP-LEFT (common in table tops)
        joint1 = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        # FRONT-RIGHT to BACK-RIGHT (common in frames)
        joint2 = AlignedScrewJoint(
            src_face=Face.FRONT,
            dst_face=Face.BACK,
            src_edge_point=EdgePoint(Face.FRONT, Face.RIGHT, 0.3),
            dst_edge_point=EdgePoint(Face.BACK, Face.RIGHT, 0.3),
        )

        # TOP-FRONT to BOTTOM-FRONT (vertical connections)
        joint3 = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.BOTTOM,
            src_edge_point=EdgePoint(Face.TOP, Face.FRONT, 0.8),
            dst_edge_point=EdgePoint(Face.BOTTOM, Face.FRONT, 0.8),
        )

        # All should be valid joints
        assert isinstance(joint1, AlignedScrewJoint)
        assert isinstance(joint2, AlignedScrewJoint)
        assert isinstance(joint3, AlignedScrewJoint)

    def test_edge_pointitions_at_boundaries(self):
        """Test edge positions at start and end of edges."""
        # Joint at the start of edges
        joint_start = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.0),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.0),
        )

        # Joint at the end of edges
        joint_end = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 1.0),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 1.0),
        )

        assert joint_start.src_edge_point.position == 0.0
        assert joint_end.src_edge_point.position == 1.0
