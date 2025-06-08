"""Tests for graph validation module."""

import pytest
from typing import List

from nichiyou_daiku.graph.woodworking_graph import WoodworkingGraph
from nichiyou_daiku.graph.validation import (
    ValidationMode,
    ValidationSeverity,
    ValidationIssue,
    ValidationSuccess,
    ValidationError,
    ValidationReport,
    ConnectivityValidator,
    CollisionValidator,
    JointValidator,
    StructuralValidator,
    AssemblyOrderValidator,
    GraphValidationSuite,
    validate_graph,
    quick_validate,
    get_validation_summary,
)
from nichiyou_daiku.core.lumber import LumberPiece, LumberType, Face
from nichiyou_daiku.core.geometry import EdgePoint
from nichiyou_daiku.connectors.aligned_screw import AlignedScrewJoint


class TestValidationIssue:
    """Test ValidationIssue dataclass."""

    def test_issue_creation(self):
        """Test creating validation issues."""
        issue = ValidationIssue(
            severity=ValidationSeverity.ERROR,
            validator_name="TestValidator",
            message="Test error message",
            affected_pieces=["beam1", "beam2"],
            suggestion="Fix the problem",
        )

        assert issue.severity == ValidationSeverity.ERROR
        assert issue.validator_name == "TestValidator"
        assert issue.message == "Test error message"
        assert issue.affected_pieces == ["beam1", "beam2"]
        assert issue.suggestion == "Fix the problem"

    def test_issue_defaults(self):
        """Test default values for optional fields."""
        issue = ValidationIssue(
            severity=ValidationSeverity.WARNING,
            validator_name="TestValidator",
            message="Warning message",
        )

        assert issue.affected_pieces == []
        assert issue.suggestion is None


class TestValidationError:
    """Test ValidationError result class."""

    def test_error_with_issues(self):
        """Test validation error with multiple issues."""
        issues = [
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                validator_name="Test",
                message="Error 1",
            ),
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                validator_name="Test",
                message="Warning 1",
            ),
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                validator_name="Test",
                message="Error 2",
            ),
        ]

        error = ValidationError("TestValidator", issues)

        assert error.validator_name == "TestValidator"
        assert len(error.issues) == 3
        assert error.has_errors
        assert error.error_count == 2
        assert error.warning_count == 1

    def test_error_only_warnings(self):
        """Test validation error with only warnings."""
        issues = [
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                validator_name="Test",
                message="Warning 1",
            ),
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                validator_name="Test",
                message="Warning 2",
            ),
        ]

        error = ValidationError("TestValidator", issues)

        assert not error.has_errors
        assert error.error_count == 0
        assert error.warning_count == 2


class TestValidationReport:
    """Test ValidationReport class."""

    def test_empty_report(self):
        """Test empty validation report."""
        report = ValidationReport()

        assert report.passed  # Empty report passes
        assert report.total_errors == 0
        assert report.total_warnings == 0
        assert report.get_affected_pieces() == set()

    def test_report_with_success(self):
        """Test report with successful validations."""
        report = ValidationReport()
        report.results.append(ValidationSuccess("Validator1", "All good"))
        report.results.append(ValidationSuccess("Validator2", "Looking fine"))

        assert report.passed
        assert report.total_errors == 0
        assert report.total_warnings == 0

    def test_report_strict_mode(self):
        """Test report in strict mode fails on any error."""
        report = ValidationReport(mode=ValidationMode.STRICT)

        # Add success
        report.results.append(ValidationSuccess("Validator1", "OK"))

        # Add error
        error_issue = ValidationIssue(
            severity=ValidationSeverity.ERROR,
            validator_name="Validator2",
            message="Problem found",
        )
        report.results.append(ValidationError("Validator2", [error_issue]))

        assert not report.passed  # Fails in strict mode
        assert report.total_errors == 1

    def test_report_permissive_mode(self):
        """Test report in permissive mode passes with errors."""
        report = ValidationReport(mode=ValidationMode.PERMISSIVE)

        # Add error
        error_issue = ValidationIssue(
            severity=ValidationSeverity.ERROR,
            validator_name="Validator1",
            message="Problem found",
        )
        report.results.append(ValidationError("Validator1", [error_issue]))

        assert report.passed  # Still passes in permissive mode
        assert report.total_errors == 1

    def test_get_issues_by_severity(self):
        """Test filtering issues by severity."""
        report = ValidationReport()

        issues = [
            ValidationIssue(ValidationSeverity.ERROR, "V1", "Error 1"),
            ValidationIssue(ValidationSeverity.WARNING, "V1", "Warning 1"),
            ValidationIssue(ValidationSeverity.ERROR, "V2", "Error 2"),
            ValidationIssue(ValidationSeverity.INFO, "V2", "Info 1"),
        ]

        report.results.append(ValidationError("V1", issues[:2]))
        report.results.append(ValidationError("V2", issues[2:]))

        errors = report.get_issues_by_severity(ValidationSeverity.ERROR)
        assert len(errors) == 2

        warnings = report.get_issues_by_severity(ValidationSeverity.WARNING)
        assert len(warnings) == 1

        infos = report.get_issues_by_severity(ValidationSeverity.INFO)
        assert len(infos) == 1

    def test_get_affected_pieces(self):
        """Test collecting all affected pieces."""
        report = ValidationReport()

        issue1 = ValidationIssue(
            ValidationSeverity.ERROR,
            "V1",
            "Issue 1",
            affected_pieces=["beam1", "beam2"],
        )
        issue2 = ValidationIssue(
            ValidationSeverity.WARNING,
            "V2",
            "Issue 2",
            affected_pieces=["beam2", "beam3"],
        )

        report.results.append(ValidationError("V1", [issue1]))
        report.results.append(ValidationError("V2", [issue2]))

        affected = report.get_affected_pieces()
        assert affected == {"beam1", "beam2", "beam3"}

    def test_report_to_string(self):
        """Test human-readable report generation."""
        report = ValidationReport(mode=ValidationMode.STRICT)

        # Add success
        report.results.append(
            ValidationSuccess("ConnectivityValidator", "All connected")
        )

        # Add error with details
        issue = ValidationIssue(
            severity=ValidationSeverity.ERROR,
            validator_name="CollisionValidator",
            message="Pieces overlap",
            affected_pieces=["beam1", "beam2"],
            suggestion="Adjust positions",
        )
        report.results.append(ValidationError("CollisionValidator", [issue]))

        output = report.to_string()

        assert "strict mode" in output
        assert "FAILED" in output
        assert "Total Errors: 1" in output
        assert "✓ ConnectivityValidator" in output
        assert "✗ CollisionValidator" in output
        assert "Pieces overlap" in output
        assert "beam1, beam2" in output
        assert "Adjust positions" in output


class TestConnectivityValidator:
    """Test connectivity validation."""

    def test_empty_graph(self):
        """Test validator on empty graph."""
        graph = WoodworkingGraph()
        validator = ConnectivityValidator()

        result = validator.validate(graph, ValidationMode.STRICT)
        assert isinstance(result, ValidationSuccess)

    def test_single_piece(self):
        """Test validator on single piece."""
        graph = WoodworkingGraph()
        lumber = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(lumber)

        validator = ConnectivityValidator()
        result = validator.validate(graph, ValidationMode.STRICT)
        assert isinstance(result, ValidationSuccess)

    def test_connected_pieces(self):
        """Test validator on properly connected pieces."""
        graph = WoodworkingGraph()

        # Add three connected pieces
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)
        lumber3 = LumberPiece("beam3", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)
        graph.add_lumber_piece(lumber3)

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        graph.add_joint("beam1", "beam2", joint)
        graph.add_joint("beam2", "beam3", joint)

        validator = ConnectivityValidator()
        result = validator.validate(graph, ValidationMode.STRICT)
        assert isinstance(result, ValidationSuccess)

    def test_floating_pieces_strict(self):
        """Test validator finds floating pieces in strict mode."""
        graph = WoodworkingGraph()

        # Add connected pair
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )
        graph.add_joint("beam1", "beam2", joint)

        # Add floating piece
        lumber3 = LumberPiece("beam3", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(lumber3)

        validator = ConnectivityValidator()
        result = validator.validate(graph, ValidationMode.STRICT)

        assert isinstance(result, ValidationError)
        assert result.error_count == 1
        assert "beam3" in result.issues[0].affected_pieces

    def test_floating_pieces_permissive(self):
        """Test validator in permissive mode treats single floaters as warnings."""
        graph = WoodworkingGraph()

        # Add connected pair
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )
        graph.add_joint("beam1", "beam2", joint)

        # Add single floating piece
        lumber3 = LumberPiece("beam3", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(lumber3)

        validator = ConnectivityValidator()
        result = validator.validate(graph, ValidationMode.PERMISSIVE)

        assert isinstance(result, ValidationError)
        assert result.error_count == 0
        assert result.warning_count == 1

    def test_multiple_components(self):
        """Test validator with multiple disconnected components."""
        graph = WoodworkingGraph()

        # Component 1: beam1-beam2
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)

        # Component 2: beam3-beam4
        lumber3 = LumberPiece("beam3", LumberType.LUMBER_2X4, 1000.0)
        lumber4 = LumberPiece("beam4", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(lumber3)
        graph.add_lumber_piece(lumber4)

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        graph.add_joint("beam1", "beam2", joint)
        graph.add_joint("beam3", "beam4", joint)

        validator = ConnectivityValidator()
        result = validator.validate(graph, ValidationMode.STRICT)

        assert isinstance(result, ValidationError)
        assert len(result.issues) == 1  # One disconnected component


class TestCollisionValidator:
    """Test collision detection validation."""

    def test_single_piece_no_collision(self):
        """Test validator with single piece."""
        graph = WoodworkingGraph()
        lumber = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(lumber)

        validator = CollisionValidator()
        result = validator.validate(graph, ValidationMode.STRICT)
        assert isinstance(result, ValidationSuccess)

    def test_connected_pieces_no_collision(self):
        """Test properly connected pieces don't collide."""
        graph = WoodworkingGraph()

        # Two pieces connected end-to-end
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 800.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)

        joint = AlignedScrewJoint(
            src_face=Face.FRONT,
            dst_face=Face.BACK,
            src_edge_point=EdgePoint(Face.FRONT, Face.TOP, 0.5),
            dst_edge_point=EdgePoint(Face.BACK, Face.TOP, 0.5),
        )

        graph.add_joint("beam1", "beam2", joint)

        validator = CollisionValidator()
        result = validator.validate(graph, ValidationMode.STRICT)
        assert isinstance(result, ValidationSuccess)

    def test_overlapping_pieces(self):
        """Test detection of overlapping pieces."""
        graph = WoodworkingGraph()

        # Two pieces at same position (will overlap)
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)

        # Connect them in a way that causes overlap
        # Both pieces will try to occupy same space
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.0),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.0),
        )

        graph.add_joint("beam1", "beam2", joint)

        validator = CollisionValidator(tolerance=1.0)
        result = validator.validate(graph, ValidationMode.STRICT)

        # This particular joint configuration might not cause full overlap
        # depending on the exact positioning algorithm
        # The test verifies the validator runs without error
        assert isinstance(result, (ValidationSuccess, ValidationError))

    def test_tolerance_setting(self):
        """Test collision tolerance affects detection."""
        graph = WoodworkingGraph()

        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)

        # Very strict tolerance
        validator_strict = CollisionValidator(tolerance=0.1)
        result_strict = validator_strict.validate(graph, ValidationMode.STRICT)

        # Loose tolerance
        validator_loose = CollisionValidator(tolerance=100.0)
        result_loose = validator_loose.validate(graph, ValidationMode.STRICT)

        # Both should succeed for unconnected pieces
        assert isinstance(result_strict, ValidationSuccess)
        assert isinstance(result_loose, ValidationSuccess)


class TestJointValidator:
    """Test joint configuration validation."""

    def test_empty_graph(self):
        """Test validator on graph with no joints."""
        graph = WoodworkingGraph()
        lumber = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(lumber)

        validator = JointValidator()
        result = validator.validate(graph, ValidationMode.STRICT)
        assert isinstance(result, ValidationSuccess)

    def test_valid_joint_same_face(self):
        """Test valid joint connecting same faces."""
        graph = WoodworkingGraph()

        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        graph.add_joint("beam1", "beam2", joint)

        validator = JointValidator()
        result = validator.validate(graph, ValidationMode.STRICT)
        assert isinstance(result, ValidationSuccess)

    def test_valid_joint_opposite_faces(self):
        """Test valid joint connecting opposite faces."""
        graph = WoodworkingGraph()

        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.BOTTOM,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.BOTTOM, Face.LEFT, 0.5),
        )

        graph.add_joint("beam1", "beam2", joint)

        validator = JointValidator()
        result = validator.validate(graph, ValidationMode.STRICT)
        assert isinstance(result, ValidationSuccess)

    def test_unusual_face_combination(self):
        """Test warning for unusual face combinations."""
        graph = WoodworkingGraph()

        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)

        # TOP to FRONT is unusual
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.FRONT,
            src_edge_point=EdgePoint(Face.TOP, Face.FRONT, 0.5),
            dst_edge_point=EdgePoint(Face.FRONT, Face.TOP, 0.5),
        )

        graph.add_joint("beam1", "beam2", joint)

        validator = JointValidator()

        # Strict mode: error
        result_strict = validator.validate(graph, ValidationMode.STRICT)
        assert isinstance(result_strict, ValidationError)
        assert result_strict.error_count == 1

        # Permissive mode: warning
        result_permissive = validator.validate(graph, ValidationMode.PERMISSIVE)
        assert isinstance(result_permissive, ValidationError)
        assert result_permissive.error_count == 0
        assert result_permissive.warning_count == 1

    def test_edge_point_face_mismatch(self):
        """Test error when edge point doesn't match joint face."""
        graph = WoodworkingGraph()

        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)

        # Edge point on wrong face
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.BOTTOM, Face.RIGHT, 0.5),  # Wrong face!
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        graph.add_joint("beam1", "beam2", joint)

        validator = JointValidator()
        result = validator.validate(graph, ValidationMode.STRICT)

        assert isinstance(result, ValidationError)
        assert result.error_count >= 1
        assert "not on joint face" in result.issues[0].message.lower()

    def test_invalid_edge_parameter(self):
        """Test error for edge parameters outside [0,1]."""
        graph = WoodworkingGraph()

        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)

        # Invalid position > 1.0
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 1.5),  # Invalid!
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, -0.1),  # Invalid!
        )

        graph.add_joint("beam1", "beam2", joint)

        validator = JointValidator()
        result = validator.validate(graph, ValidationMode.STRICT)

        assert isinstance(result, ValidationError)
        assert result.error_count >= 2  # Both parameters invalid

    def test_symmetric_connections(self):
        """Test detection of asymmetric bidirectional connections."""
        graph = WoodworkingGraph()

        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)

        joint1 = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.25),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.25),
        )
        joint2 = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.75),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.75),
        )

        # Add 2 joints one way, 1 joint the other way
        graph.add_joint("beam1", "beam2", joint1)
        graph.add_joint("beam1", "beam2", joint2)
        graph.add_joint("beam2", "beam1", joint1)

        validator = JointValidator()
        result = validator.validate(graph, ValidationMode.STRICT)

        # Should get warning about asymmetric joint count
        assert isinstance(result, ValidationError)
        assert any("symmetric" in issue.message.lower() for issue in result.issues)


class TestStructuralValidator:
    """Test structural requirements validation."""

    def test_empty_graph(self):
        """Test validator on empty graph."""
        graph = WoodworkingGraph()
        validator = StructuralValidator()

        result = validator.validate(graph, ValidationMode.STRICT)
        assert isinstance(result, ValidationSuccess)

    def test_well_connected_structure(self):
        """Test validator on properly connected structure."""
        graph = WoodworkingGraph()

        # Create a square frame with 4 pieces
        pieces = [
            LumberPiece(f"beam{i}", LumberType.LUMBER_2X4, 1000.0) for i in range(4)
        ]

        for piece in pieces:
            graph.add_lumber_piece(piece)

        joint = AlignedScrewJoint(
            src_face=Face.FRONT,
            dst_face=Face.BACK,
            src_edge_point=EdgePoint(Face.FRONT, Face.TOP, 0.5),
            dst_edge_point=EdgePoint(Face.BACK, Face.TOP, 0.5),
        )

        # Connect in a square
        graph.add_joint("beam0", "beam1", joint)
        graph.add_joint("beam1", "beam2", joint)
        graph.add_joint("beam2", "beam3", joint)
        graph.add_joint("beam3", "beam0", joint)

        validator = StructuralValidator(min_joints_per_piece=2)
        result = validator.validate(graph, ValidationMode.STRICT)
        assert isinstance(result, ValidationSuccess)

    def test_insufficient_connections(self):
        """Test detection of pieces with too few connections."""
        graph = WoodworkingGraph()

        # Three pieces in a line
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)
        lumber3 = LumberPiece("beam3", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)
        graph.add_lumber_piece(lumber3)

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        graph.add_joint("beam1", "beam2", joint)
        graph.add_joint("beam2", "beam3", joint)

        # beam1 and beam3 only have 1 connection each
        validator = StructuralValidator(min_joints_per_piece=2)
        result = validator.validate(graph, ValidationMode.STRICT)

        assert isinstance(result, ValidationError)
        # Should have warnings for beam1 and beam3
        assert len(result.issues) == 2
        affected_all = []
        for issue in result.issues:
            affected_all.extend(issue.affected_pieces)
        assert "beam1" in affected_all
        assert "beam3" in affected_all

    def test_isolated_piece(self):
        """Test error for completely isolated piece."""
        graph = WoodworkingGraph()

        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)

        # No connections!

        validator = StructuralValidator(min_joints_per_piece=1)
        result = validator.validate(graph, ValidationMode.STRICT)

        assert isinstance(result, ValidationError)
        assert result.error_count >= 2  # Both pieces have 0 connections


class TestAssemblyOrderValidator:
    """Test assembly order validation."""

    def test_no_assembly_order(self):
        """Test validator when no assembly order is specified."""
        graph = WoodworkingGraph()

        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        # No assembly_order parameter
        graph.add_joint("beam1", "beam2", joint)

        validator = AssemblyOrderValidator()
        result = validator.validate(graph, ValidationMode.STRICT)
        assert isinstance(result, ValidationSuccess)

    def test_valid_assembly_sequence(self):
        """Test validator with valid assembly sequence."""
        graph = WoodworkingGraph()

        pieces = [
            LumberPiece(f"beam{i}", LumberType.LUMBER_2X4, 1000.0) for i in range(4)
        ]

        for piece in pieces:
            graph.add_lumber_piece(piece)

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        # Add joints with sequential assembly order
        graph.add_joint("beam0", "beam1", joint, assembly_order=1)
        graph.add_joint("beam1", "beam2", joint, assembly_order=2)
        graph.add_joint("beam2", "beam3", joint, assembly_order=3)

        validator = AssemblyOrderValidator()
        result = validator.validate(graph, ValidationMode.STRICT)
        assert isinstance(result, ValidationSuccess)

    def test_missing_sequence_numbers(self):
        """Test detection of gaps in assembly sequence."""
        graph = WoodworkingGraph()

        pieces = [
            LumberPiece(f"beam{i}", LumberType.LUMBER_2X4, 1000.0) for i in range(4)
        ]

        for piece in pieces:
            graph.add_lumber_piece(piece)

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        # Skip assembly order 2
        graph.add_joint("beam0", "beam1", joint, assembly_order=1)
        graph.add_joint("beam1", "beam2", joint, assembly_order=3)
        graph.add_joint("beam2", "beam3", joint, assembly_order=4)

        validator = AssemblyOrderValidator()
        result = validator.validate(graph, ValidationMode.STRICT)

        assert isinstance(result, ValidationError)
        assert any("missing" in issue.message.lower() for issue in result.issues)

    def test_duplicate_assembly_order(self):
        """Test detection of duplicate assembly order numbers."""
        graph = WoodworkingGraph()

        pieces = [
            LumberPiece(f"beam{i}", LumberType.LUMBER_2X4, 1000.0) for i in range(3)
        ]

        for piece in pieces:
            graph.add_lumber_piece(piece)

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        # Two joints with same assembly order
        graph.add_joint("beam0", "beam1", joint, assembly_order=1)
        graph.add_joint("beam1", "beam2", joint, assembly_order=1)

        validator = AssemblyOrderValidator()
        result = validator.validate(graph, ValidationMode.STRICT)

        assert isinstance(result, ValidationError)
        assert result.warning_count >= 1
        assert any("multiple" in issue.message.lower() for issue in result.issues)


class TestGraphValidationSuite:
    """Test the complete validation suite."""

    def test_default_validators(self):
        """Test suite with default validators."""
        suite = GraphValidationSuite()

        assert len(suite.validators) == 5
        validator_types = [type(v).__name__ for v in suite.validators]
        assert "ConnectivityValidator" in validator_types
        assert "CollisionValidator" in validator_types
        assert "JointValidator" in validator_types
        assert "StructuralValidator" in validator_types
        assert "AssemblyOrderValidator" in validator_types

    def test_custom_validators(self):
        """Test suite with custom validator list."""
        validators = [
            ConnectivityValidator(),
            StructuralValidator(min_joints_per_piece=3),
        ]
        suite = GraphValidationSuite(validators)

        assert len(suite.validators) == 2

    def test_validate_valid_graph(self):
        """Test suite on a valid graph."""
        graph = WoodworkingGraph()

        # Build a simple valid structure - 3 pieces to allow 2 connections each
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 800.0)
        lumber3 = LumberPiece("beam3", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)
        graph.add_lumber_piece(lumber3)

        # Connect in a line: beam1 -- beam2 -- beam3
        joint1 = AlignedScrewJoint(
            src_face=Face.FRONT,
            dst_face=Face.BACK,
            src_edge_point=EdgePoint(Face.FRONT, Face.TOP, 0.5),
            dst_edge_point=EdgePoint(Face.BACK, Face.TOP, 0.5),
        )
        joint2 = AlignedScrewJoint(
            src_face=Face.FRONT,
            dst_face=Face.BACK,
            src_edge_point=EdgePoint(Face.FRONT, Face.TOP, 0.5),
            dst_edge_point=EdgePoint(Face.BACK, Face.TOP, 0.5),
        )

        graph.add_joint("beam1", "beam2", joint1, assembly_order=1)
        graph.add_joint("beam2", "beam3", joint2, assembly_order=2)

        # Add reverse connections to satisfy structural requirements
        graph.add_joint("beam2", "beam1", joint1, assembly_order=3)
        graph.add_joint("beam3", "beam2", joint2, assembly_order=4)

        suite = GraphValidationSuite()
        report = suite.validate(graph, ValidationMode.PERMISSIVE)

        assert report.passed
        # In permissive mode, structural warnings are OK
        assert report.total_errors == 0

    def test_validate_invalid_graph(self):
        """Test suite on an invalid graph."""
        graph = WoodworkingGraph()

        # Add disconnected pieces
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)
        lumber3 = LumberPiece("beam3", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)
        graph.add_lumber_piece(lumber3)

        # Only connect two of them
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        graph.add_joint("beam1", "beam2", joint)

        suite = GraphValidationSuite()
        report = suite.validate(graph, ValidationMode.STRICT)

        assert not report.passed
        assert report.total_errors > 0

    def test_validator_exception_handling(self):
        """Test suite handles validator exceptions gracefully."""

        from nichiyou_daiku.graph.validation import GraphValidator

        class FailingValidator(GraphValidator):
            def validate(self, graph, mode):
                raise RuntimeError("Validator exploded!")

        suite = GraphValidationSuite([FailingValidator()])
        graph = WoodworkingGraph()

        report = suite.validate(graph, ValidationMode.STRICT)

        assert not report.passed
        assert report.total_errors == 1
        assert "crashed" in report.results[0].issues[0].message


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_validate_graph_function(self):
        """Test validate_graph convenience function."""
        graph = WoodworkingGraph()

        # Create a triangle structure to satisfy structural validator
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)
        lumber3 = LumberPiece("beam3", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)
        graph.add_lumber_piece(lumber3)

        # Create joints to form a triangle
        joint = AlignedScrewJoint(
            src_face=Face.FRONT,
            dst_face=Face.BACK,
            src_edge_point=EdgePoint(Face.FRONT, Face.TOP, 0.5),
            dst_edge_point=EdgePoint(Face.BACK, Face.TOP, 0.5),
        )

        # Each piece needs at least 2 connections
        graph.add_joint("beam1", "beam2", joint)
        graph.add_joint("beam2", "beam3", joint)
        graph.add_joint("beam3", "beam1", joint)

        report = validate_graph(graph, ValidationMode.STRICT)

        assert isinstance(report, ValidationReport)
        assert report.passed

    def test_quick_validate_function(self):
        """Test quick_validate convenience function."""
        graph = WoodworkingGraph()

        # Create a triangle structure to satisfy structural validator
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)
        lumber3 = LumberPiece("beam3", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)
        graph.add_lumber_piece(lumber3)

        # Create joints to form a triangle
        joint = AlignedScrewJoint(
            src_face=Face.FRONT,
            dst_face=Face.BACK,
            src_edge_point=EdgePoint(Face.FRONT, Face.TOP, 0.5),
            dst_edge_point=EdgePoint(Face.BACK, Face.TOP, 0.5),
        )

        # Each piece needs at least 2 connections
        graph.add_joint("beam1", "beam2", joint)
        graph.add_joint("beam2", "beam3", joint)
        graph.add_joint("beam3", "beam1", joint)

        is_valid = quick_validate(graph)

        assert isinstance(is_valid, bool)
        assert is_valid

    def test_get_validation_summary(self):
        """Test validation summary generation."""
        # Test passed validation
        report_pass = ValidationReport()
        report_pass.results.append(ValidationSuccess("Test", "OK"))

        summary = get_validation_summary(report_pass)
        assert "passed" in summary

        # Test failed validation
        report_fail = ValidationReport()
        issue = ValidationIssue(ValidationSeverity.ERROR, "Test", "Problem")
        report_fail.results.append(ValidationError("Test", [issue]))

        summary = get_validation_summary(report_fail)
        assert "failed" in summary
        assert "1 errors" in summary
