"""Tests for aligned wood screw connector."""


from nichiyou_daiku.connectors.aligned_screw import (
    AlignedScrewJoint,
    calculate_screw_positions,
    validate_edge_alignment,
    generate_drill_points,
    DrillPoint,
    EdgeAlignment,
)
from nichiyou_daiku.core.lumber import Face
from nichiyou_daiku.core.geometry import EdgePosition


class TestEdgeAlignment:
    """Test edge alignment validation."""

    def test_valid_edge_alignment_same_length(self):
        """Test valid alignment when edges have same length."""
        # Both pieces 1000mm long, aligned at TOP-RIGHT edges
        edge1 = EdgePosition(Face.TOP, Face.RIGHT)
        edge2 = EdgePosition(Face.TOP, Face.LEFT)
        length1 = 1000.0
        length2 = 1000.0

        alignment = validate_edge_alignment(edge1, edge2, length1, length2)

        assert alignment is not None
        assert alignment.edge1 == edge1
        assert alignment.edge2 == edge2
        assert alignment.overlap_start == 0.0
        assert alignment.overlap_end == 1000.0
        assert alignment.overlap_length == 1000.0

    def test_valid_edge_alignment_partial_overlap(self):
        """Test valid alignment with partial overlap."""
        edge1 = EdgePosition(Face.TOP, Face.RIGHT)
        edge2 = EdgePosition(Face.TOP, Face.LEFT)
        length1 = 1000.0
        length2 = 600.0
        offset = 200.0  # Second piece starts 200mm from start of first

        alignment = validate_edge_alignment(
            edge1, edge2, length1, length2, offset2=offset
        )

        assert alignment is not None
        assert alignment.overlap_start == 200.0
        assert alignment.overlap_end == 800.0
        assert alignment.overlap_length == 600.0

    def test_invalid_edge_alignment_no_overlap(self):
        """Test invalid alignment when edges don't overlap."""
        edge1 = EdgePosition(Face.TOP, Face.RIGHT)
        edge2 = EdgePosition(Face.TOP, Face.LEFT)
        length1 = 500.0
        length2 = 500.0
        offset = 600.0  # Second piece starts after first ends

        alignment = validate_edge_alignment(
            edge1, edge2, length1, length2, offset2=offset
        )

        assert alignment is None

    def test_invalid_edge_alignment_incompatible_edges(self):
        """Test invalid alignment with incompatible edge types."""
        # TOP-RIGHT edge can't align with FRONT-BACK edge
        edge1 = EdgePosition(Face.TOP, Face.RIGHT)
        edge2 = EdgePosition(Face.FRONT, Face.BACK)

        alignment = validate_edge_alignment(edge1, edge2, 1000.0, 1000.0)

        assert alignment is None


class TestScrewPositions:
    """Test screw position calculations."""

    def test_calculate_screw_positions_single(self):
        """Test single screw position calculation."""
        positions = calculate_screw_positions(
            overlap_start=0.0, overlap_end=100.0, screw_count=1, edge_inset=25.0
        )

        assert len(positions) == 1
        assert positions[0] == 50.0  # Centered

    def test_calculate_screw_positions_multiple(self):
        """Test multiple screw position calculation."""
        positions = calculate_screw_positions(
            overlap_start=0.0, overlap_end=300.0, screw_count=3, edge_inset=50.0
        )

        assert len(positions) == 3
        assert positions[0] == 50.0  # First at inset
        assert positions[1] == 150.0  # Middle
        assert positions[2] == 250.0  # Last at end-inset

    def test_calculate_screw_positions_auto_count(self):
        """Test automatic screw count based on length."""
        # Should use ~150mm spacing
        positions = calculate_screw_positions(
            overlap_start=0.0, overlap_end=500.0, screw_count=None, edge_inset=50.0
        )

        assert len(positions) == 3  # 50, 250, 450
        assert positions[0] == 50.0
        assert positions[-1] == 450.0

    def test_calculate_screw_positions_minimum_spacing(self):
        """Test that minimum spacing is enforced."""
        # Request too many screws for the length
        positions = calculate_screw_positions(
            overlap_start=0.0,
            overlap_end=200.0,
            screw_count=10,  # Would be only 20mm apart
            edge_inset=25.0,
        )

        # Should reduce to maintain minimum spacing
        assert len(positions) < 10
        assert all(
            positions[i + 1] - positions[i] >= 50.0 for i in range(len(positions) - 1)
        )


class TestDrillPoints:
    """Test drill point generation."""

    def test_generate_drill_points_basic(self):
        """Test basic drill point generation."""
        alignment = EdgeAlignment(
            edge1=EdgePosition(Face.TOP, Face.RIGHT),
            edge2=EdgePosition(Face.TOP, Face.LEFT),
            overlap_start=0.0,
            overlap_end=200.0,
            overlap_length=200.0,
        )

        points = generate_drill_points(
            alignment, screw_diameter=4.0, pilot_diameter=3.0, screw_count=2
        )

        assert len(points) == 4  # 2 pilot + 2 clearance

        # Check pilot holes (first piece)
        pilots = [p for p in points if p.diameter == 3.0]
        assert len(pilots) == 2
        assert all(p.edge_position.face1 == Face.TOP for p in pilots)
        assert all(p.edge_position.face2 == Face.RIGHT for p in pilots)

        # Check clearance holes (second piece)
        clearances = [p for p in points if p.diameter == 4.0]
        assert len(clearances) == 2
        assert all(p.edge_position.face1 == Face.TOP for p in clearances)
        assert all(p.edge_position.face2 == Face.LEFT for p in clearances)

    def test_generate_drill_points_with_offset(self):
        """Test drill points with offset alignment."""
        alignment = EdgeAlignment(
            edge1=EdgePosition(Face.FRONT, Face.RIGHT),
            edge2=EdgePosition(Face.FRONT, Face.LEFT),
            overlap_start=100.0,
            overlap_end=400.0,
            overlap_length=300.0,
        )

        points = generate_drill_points(
            alignment, screw_diameter=5.0, pilot_diameter=3.5
        )

        # Should auto-calculate 2 screws for 300mm
        assert len(points) == 4

        # Check positions are within overlap range
        for point in points:
            assert 100.0 <= point.position <= 400.0


class TestAlignedScrewJoint:
    """Test the complete aligned screw joint."""

    def test_joint_creation(self):
        """Test creating an aligned screw joint."""
        joint = AlignedScrewJoint(
            edge1=EdgePosition(Face.TOP, Face.RIGHT),
            edge2=EdgePosition(Face.TOP, Face.LEFT),  # Share TOP face
            overlap_start=50.0,
            overlap_end=250.0,
            screw_diameter=4.0,
            screw_count=2,
        )

        assert joint.alignment.overlap_length == 200.0
        assert joint.screw_diameter == 4.0
        assert joint.screw_count == 2

    def test_joint_drill_points(self):
        """Test getting drill points from joint."""
        joint = AlignedScrewJoint(
            edge1=EdgePosition(Face.TOP, Face.RIGHT),
            edge2=EdgePosition(Face.TOP, Face.LEFT),
            overlap_start=0.0,
            overlap_end=300.0,
            screw_diameter=4.5,
            screw_count=3,
        )

        points = joint.drill_points

        assert len(points) == 6  # 3 pilot + 3 clearance
        assert all(isinstance(p, DrillPoint) for p in points)

    def test_joint_equality(self):
        """Test joint equality comparison."""
        edge1 = EdgePosition(Face.TOP, Face.RIGHT)
        edge2 = EdgePosition(Face.TOP, Face.LEFT)

        joint1 = AlignedScrewJoint(edge1, edge2, 0.0, 100.0, 4.0, 1)
        joint2 = AlignedScrewJoint(edge1, edge2, 0.0, 100.0, 4.0, 1)
        joint3 = AlignedScrewJoint(edge1, edge2, 0.0, 100.0, 5.0, 1)

        assert joint1 == joint2
        assert joint1 != joint3


class TestFunctionalHelpers:
    """Test functional helper functions."""

    def test_edge_alignment_compatible_edges(self):
        """Test alignment of edges that share a face and run in same direction."""
        # TOP-RIGHT edge should align with BOTTOM-RIGHT edge (both WIDTH_WISE, share RIGHT)
        edge1 = EdgePosition(Face.TOP, Face.RIGHT)
        edge2 = EdgePosition(Face.BOTTOM, Face.RIGHT)

        alignment = validate_edge_alignment(edge1, edge2, 500.0, 500.0)

        assert alignment is not None
        assert alignment.overlap_length == 500.0

    def test_minimum_overlap_requirement(self):
        """Test that minimum overlap is enforced."""
        edge1 = EdgePosition(Face.TOP, Face.RIGHT)
        edge2 = EdgePosition(Face.TOP, Face.LEFT)

        # Very small overlap
        alignment = validate_edge_alignment(edge1, edge2, 1000.0, 100.0, offset2=950.0)

        # Should still be valid if overlap >= 50mm
        assert alignment is not None
        assert alignment.overlap_length == 50.0

        # Too small overlap
        alignment2 = validate_edge_alignment(edge1, edge2, 1000.0, 100.0, offset2=960.0)

        assert alignment2 is None  # Less than minimum
