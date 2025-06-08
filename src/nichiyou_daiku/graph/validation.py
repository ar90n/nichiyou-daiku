"""Graph validation and consistency checking for woodworking assemblies.

This module provides validators to ensure woodworking graphs represent
physically possible and structurally sound assemblies.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple, Union
from enum import Enum
import logging

from nichiyou_daiku.graph.woodworking_graph import (
    WoodworkingGraph,
    calculate_piece_origin_position,
)
from nichiyou_daiku.core.lumber import Face
from nichiyou_daiku.core.geometry import EdgePoint


# Type aliases
Position3D = Tuple[float, float, float]
ValidationResult = Union["ValidationSuccess", "ValidationError"]

logger = logging.getLogger(__name__)


class ValidationMode(Enum):
    """Validation strictness levels."""

    STRICT = "strict"  # All checks must pass
    PERMISSIVE = "permissive"  # Allow minor issues with warnings


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""

    ERROR = "error"  # Must be fixed
    WARNING = "warning"  # Should be addressed
    INFO = "info"  # Informational only


@dataclass(frozen=True)
class ValidationIssue:
    """A single validation issue found in the graph.

    Attributes:
        severity: How serious the issue is
        validator_name: Which validator found the issue
        message: Human-readable description of the issue
        affected_pieces: Lumber IDs involved in the issue
        suggestion: Optional suggestion for fixing the issue
    """

    severity: ValidationSeverity
    validator_name: str
    message: str
    affected_pieces: List[str] = field(default_factory=list)
    suggestion: Optional[str] = None


@dataclass(frozen=True)
class ValidationSuccess:
    """Result of successful validation."""

    validator_name: str
    message: str = "Validation passed"


@dataclass(frozen=True)
class ValidationError:
    """Result of failed validation with issues."""

    validator_name: str
    issues: List[ValidationIssue]

    @property
    def has_errors(self) -> bool:
        """Check if any issues are errors (not just warnings)."""
        return any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)

    @property
    def error_count(self) -> int:
        """Count of error-level issues."""
        return sum(
            1 for issue in self.issues if issue.severity == ValidationSeverity.ERROR
        )

    @property
    def warning_count(self) -> int:
        """Count of warning-level issues."""
        return sum(
            1 for issue in self.issues if issue.severity == ValidationSeverity.WARNING
        )


@dataclass
class ValidationReport:
    """Complete validation report for a graph.

    Attributes:
        results: Results from all validators
        mode: Validation mode used
        passed: Whether validation passed based on mode
    """

    results: List[ValidationResult] = field(default_factory=list)
    mode: ValidationMode = ValidationMode.STRICT

    @property
    def passed(self) -> bool:
        """Check if validation passed based on mode."""
        if self.mode == ValidationMode.STRICT:
            # In strict mode, any error fails validation
            return all(
                not isinstance(result, ValidationError) or not result.has_errors
                for result in self.results
            )
        else:
            # In permissive mode, we always pass but report issues
            return True

    @property
    def total_errors(self) -> int:
        """Total count of errors across all validators."""
        return sum(
            result.error_count
            for result in self.results
            if isinstance(result, ValidationError)
        )

    @property
    def total_warnings(self) -> int:
        """Total count of warnings across all validators."""
        return sum(
            result.warning_count
            for result in self.results
            if isinstance(result, ValidationError)
        )

    def get_issues_by_severity(
        self, severity: ValidationSeverity
    ) -> List[ValidationIssue]:
        """Get all issues of a specific severity."""
        issues = []
        for result in self.results:
            if isinstance(result, ValidationError):
                issues.extend(
                    issue for issue in result.issues if issue.severity == severity
                )
        return issues

    def get_affected_pieces(self) -> Set[str]:
        """Get all lumber IDs that have validation issues."""
        affected = set()
        for result in self.results:
            if isinstance(result, ValidationError):
                for issue in result.issues:
                    affected.update(issue.affected_pieces)
        return affected

    def to_string(self) -> str:
        """Generate human-readable report."""
        lines = [
            f"Validation Report ({self.mode.value} mode)",
            f"{'=' * 40}",
        ]

        if self.passed:
            lines.append("✓ Validation PASSED")
        else:
            lines.append("✗ Validation FAILED")

        lines.extend(
            [
                f"Total Errors: {self.total_errors}",
                f"Total Warnings: {self.total_warnings}",
                "",
            ]
        )

        # Group results by validator
        for result in self.results:
            if isinstance(result, ValidationSuccess):
                lines.append(f"✓ {result.validator_name}: {result.message}")
            else:
                lines.append(f"✗ {result.validator_name}:")
                for issue in result.issues:
                    icon = (
                        "  ❌" if issue.severity == ValidationSeverity.ERROR else "  ⚠️"
                    )
                    lines.append(f"{icon} {issue.message}")
                    if issue.affected_pieces:
                        lines.append(
                            f"     Affected: {', '.join(issue.affected_pieces)}"
                        )
                    if issue.suggestion:
                        lines.append(f"     Suggestion: {issue.suggestion}")

        return "\n".join(lines)


class GraphValidator(ABC):
    """Abstract base class for graph validators.

    Each validator checks a specific aspect of the graph's validity.
    """

    def __init__(self, name: Optional[str] = None):
        """Initialize validator with optional custom name."""
        self.name = name or self.__class__.__name__

    @abstractmethod
    def validate(
        self, graph: WoodworkingGraph, mode: ValidationMode
    ) -> ValidationResult:
        """Validate the graph and return results.

        Args:
            graph: The woodworking graph to validate
            mode: Validation strictness mode

        Returns:
            ValidationSuccess or ValidationError with issues found
        """
        pass


class ConnectivityValidator(GraphValidator):
    """Validates that all pieces in the graph are connected (no floating pieces).

    A valid assembly should have all pieces connected in a single component,
    unless explicitly building multiple separate assemblies.
    """

    def __init__(self):
        super().__init__("ConnectivityValidator")

    def validate(
        self, graph: WoodworkingGraph, mode: ValidationMode
    ) -> ValidationResult:
        """Check that all pieces are connected."""
        if graph.node_count() == 0:
            return ValidationSuccess(self.name, "Empty graph is trivially connected")

        if graph.node_count() == 1:
            return ValidationSuccess(self.name, "Single piece is trivially connected")

        # Find all connected components
        components = graph.get_connected_components()

        if len(components) == 1:
            return ValidationSuccess(self.name, "All pieces are connected")

        # Multiple components found - this is an issue
        issues = []

        # Find the largest component (assumed to be the main assembly)
        main_component = max(components, key=len)
        floating_components = [c for c in components if c != main_component]

        for i, component in enumerate(floating_components):
            severity = ValidationSeverity.ERROR
            if mode == ValidationMode.PERMISSIVE and len(component) == 1:
                # In permissive mode, single floating pieces are warnings
                severity = ValidationSeverity.WARNING

            issue = ValidationIssue(
                severity=severity,
                validator_name=self.name,
                message=f"Found disconnected component #{i+1} with {len(component)} piece(s)",
                affected_pieces=component,
                suggestion=f"Connect these pieces to the main assembly (containing {', '.join(main_component[:3])}{'...' if len(main_component) > 3 else ''})",
            )
            issues.append(issue)

        return ValidationError(self.name, issues)


class CollisionValidator(GraphValidator):
    """Validates that no pieces occupy the same physical space.

    Checks for overlapping lumber pieces by comparing their bounding boxes
    and actual geometry.
    """

    def __init__(self, tolerance: float = 1.0):
        """Initialize with collision tolerance.

        Args:
            tolerance: Maximum allowed overlap in mm (default 1.0mm)
        """
        super().__init__("CollisionValidator")
        self.tolerance = tolerance

    def validate(
        self, graph: WoodworkingGraph, mode: ValidationMode
    ) -> ValidationResult:
        """Check for colliding pieces."""
        if graph.node_count() < 2:
            return ValidationSuccess(self.name, "Too few pieces to have collisions")

        issues = []
        checked_pairs = set()

        # Get all connected components to check within each component
        components = graph.get_connected_components()

        for component in components:
            if len(component) < 2:
                continue

            # Use first piece in component as origin
            origin_id = component[0]

            # Check all pairs within component
            for i, piece1_id in enumerate(component):
                for piece2_id in component[i + 1 :]:
                    pair = tuple(sorted([piece1_id, piece2_id]))
                    if pair in checked_pairs:
                        continue
                    checked_pairs.add(pair)

                    # Check if these pieces are directly connected
                    directly_connected = graph.has_joint(
                        piece1_id, piece2_id
                    ) or graph.has_joint(piece2_id, piece1_id)

                    # Calculate bounding boxes
                    collision = self._check_collision(
                        graph, piece1_id, piece2_id, origin_id
                    )

                    if collision:
                        overlap_volume = collision

                        # If pieces are directly connected, small overlaps are OK
                        if directly_connected and overlap_volume < 100:  # 100 mm³
                            continue

                        severity = ValidationSeverity.ERROR
                        if mode == ValidationMode.PERMISSIVE and overlap_volume < 1000:
                            severity = ValidationSeverity.WARNING

                        issue = ValidationIssue(
                            severity=severity,
                            validator_name=self.name,
                            message=f"Pieces overlap by approximately {overlap_volume:.1f} mm³",
                            affected_pieces=[piece1_id, piece2_id],
                            suggestion="Adjust piece positions or check joint alignment",
                        )
                        issues.append(issue)

        if not issues:
            return ValidationSuccess(self.name, "No collisions detected")

        return ValidationError(self.name, issues)

    def _check_collision(
        self, graph: WoodworkingGraph, piece1_id: str, piece2_id: str, origin_id: str
    ) -> Optional[float]:
        """Check if two pieces collide and return overlap volume if they do.

        Returns None if no collision, or approximate overlap volume in mm³.
        """
        # Get piece data
        piece1 = graph.get_lumber_data(piece1_id).lumber_piece
        piece2 = graph.get_lumber_data(piece2_id).lumber_piece

        # Get dimensions
        dims1 = piece1.get_dimensions()
        dims2 = piece2.get_dimensions()

        # Get origin positions
        origin1 = calculate_piece_origin_position(graph, piece1_id, origin_id)
        origin2 = calculate_piece_origin_position(graph, piece2_id, origin_id)

        # Calculate bounding boxes (min and max corners)
        # Origin is at left-top corner of bottom face
        min1 = origin1
        max1 = (origin1[0] + dims1[2], origin1[1] + dims1[0], origin1[2] + dims1[1])

        min2 = origin2
        max2 = (origin2[0] + dims2[2], origin2[1] + dims2[0], origin2[2] + dims2[1])

        # Check for overlap in each dimension
        overlap_x = max(0, min(max1[0], max2[0]) - max(min1[0], min2[0]))
        overlap_y = max(0, min(max1[1], max2[1]) - max(min1[1], min2[1]))
        overlap_z = max(0, min(max1[2], max2[2]) - max(min1[2], min2[2]))

        # If any dimension has no overlap, boxes don't collide
        if (
            overlap_x <= self.tolerance
            or overlap_y <= self.tolerance
            or overlap_z <= self.tolerance
        ):
            return None

        # Calculate overlap volume
        overlap_volume = overlap_x * overlap_y * overlap_z

        # Only report if significant
        if overlap_volume > self.tolerance**3:
            return overlap_volume

        return None


class JointValidator(GraphValidator):
    """Validates that joints are physically possible and properly configured.

    Checks:
    - Joint faces are compatible
    - Edge points are valid
    - Symmetric connections are consistent
    """

    def __init__(self):
        super().__init__("JointValidator")

    def validate(
        self, graph: WoodworkingGraph, mode: ValidationMode
    ) -> ValidationResult:
        """Validate all joints in the graph."""
        if graph.edge_count() == 0:
            return ValidationSuccess(self.name, "No joints to validate")

        issues = []

        # Check each edge
        for src_id, dst_id, edge_data in graph._graph.edges(data=True):
            joint_data = edge_data.get("data")
            if not joint_data:
                continue

            joint = joint_data.joint

            # Validate face compatibility
            face_issue = self._validate_face_compatibility(src_id, dst_id, joint, mode)
            if face_issue:
                issues.append(face_issue)

            # Validate edge points
            edge_issues = self._validate_edge_points(graph, src_id, dst_id, joint, mode)
            issues.extend(edge_issues)

        # Check for symmetric connections
        symmetry_issues = self._validate_symmetry(graph, mode)
        issues.extend(symmetry_issues)

        if not issues:
            return ValidationSuccess(self.name, "All joints are valid")

        return ValidationError(self.name, issues)

    def _validate_face_compatibility(
        self, src_id: str, dst_id: str, joint, mode: ValidationMode
    ) -> Optional[ValidationIssue]:
        """Check if joint faces are compatible for connection."""
        # For aligned screw joints, certain face combinations don't make sense
        src_face = joint.src_face
        dst_face = joint.dst_face

        # Same face connections are OK (e.g., TOP to TOP)
        if src_face == dst_face:
            return None

        # Opposite face connections are OK
        opposite_pairs = [
            (Face.TOP, Face.BOTTOM),
            (Face.BOTTOM, Face.TOP),
            (Face.LEFT, Face.RIGHT),
            (Face.RIGHT, Face.LEFT),
            (Face.FRONT, Face.BACK),
            (Face.BACK, Face.FRONT),
        ]

        if (src_face, dst_face) in opposite_pairs:
            return None

        # Adjacent face connections need special handling
        severity = (
            ValidationSeverity.WARNING
            if mode == ValidationMode.PERMISSIVE
            else ValidationSeverity.ERROR
        )

        return ValidationIssue(
            severity=severity,
            validator_name=self.name,
            message=f"Unusual face combination: {src_face.value} to {dst_face.value}",
            affected_pieces=[src_id, dst_id],
            suggestion="Verify this joint configuration is intended",
        )

    def _validate_edge_points(
        self,
        graph: WoodworkingGraph,
        src_id: str,
        dst_id: str,
        joint,
        mode: ValidationMode,
    ) -> List[ValidationIssue]:
        """Validate edge point configurations."""
        issues = []

        # Check that edge points are on the specified faces
        src_edge = joint.src_edge_point
        dst_edge = joint.dst_edge_point

        # Check if edge point contains the joint face
        if src_edge.face1 != joint.src_face and src_edge.face2 != joint.src_face:
            issue = ValidationIssue(
                severity=ValidationSeverity.ERROR,
                validator_name=self.name,
                message=f"Source edge point not on joint face: edge is between {src_edge.face1.value} and {src_edge.face2.value}, but joint specifies {joint.src_face.value}",
                affected_pieces=[src_id],
                suggestion="Ensure edge point is on the correct face",
            )
            issues.append(issue)

        if dst_edge.face1 != joint.dst_face and dst_edge.face2 != joint.dst_face:
            issue = ValidationIssue(
                severity=ValidationSeverity.ERROR,
                validator_name=self.name,
                message=f"Destination edge point not on joint face: edge is between {dst_edge.face1.value} and {dst_edge.face2.value}, but joint specifies {joint.dst_face.value}",
                affected_pieces=[dst_id],
                suggestion="Ensure edge point is on the correct face",
            )
            issues.append(issue)

        # Check parameter ranges
        if not (0.0 <= src_edge.position <= 1.0):
            issue = ValidationIssue(
                severity=ValidationSeverity.ERROR,
                validator_name=self.name,
                message=f"Invalid source edge position: {src_edge.position}",
                affected_pieces=[src_id],
                suggestion="Edge positions must be between 0.0 and 1.0",
            )
            issues.append(issue)

        if not (0.0 <= dst_edge.position <= 1.0):
            issue = ValidationIssue(
                severity=ValidationSeverity.ERROR,
                validator_name=self.name,
                message=f"Invalid destination edge position: {dst_edge.position}",
                affected_pieces=[dst_id],
                suggestion="Edge positions must be between 0.0 and 1.0",
            )
            issues.append(issue)

        return issues

    def _validate_symmetry(
        self, graph: WoodworkingGraph, mode: ValidationMode
    ) -> List[ValidationIssue]:
        """Check for asymmetric bidirectional connections."""
        issues = []
        checked_pairs = set()

        for src_id, dst_id in graph._graph.edges():
            pair = tuple(sorted([src_id, dst_id]))
            if pair in checked_pairs:
                continue
            checked_pairs.add(pair)

            # Check if there's a reverse connection
            if graph.has_joint(dst_id, src_id):
                # Get both joints
                forward_joints = graph.get_all_joints(src_id, dst_id)
                reverse_joints = graph.get_all_joints(dst_id, src_id)

                # In most cases, bidirectional joints should be symmetric
                if len(forward_joints) != len(reverse_joints):
                    severity = ValidationSeverity.WARNING
                    issue = ValidationIssue(
                        severity=severity,
                        validator_name=self.name,
                        message=f"Asymmetric joint count: {len(forward_joints)} forward, {len(reverse_joints)} reverse",
                        affected_pieces=[src_id, dst_id],
                        suggestion="Verify if asymmetric connection is intended",
                    )
                    issues.append(issue)

        return issues


class StructuralValidator(GraphValidator):
    """Validates minimum structural requirements for stability.

    Checks:
    - Minimum number of joints per piece
    - Load path analysis
    - Support requirements
    """

    def __init__(self, min_joints_per_piece: int = 2):
        """Initialize with structural parameters.

        Args:
            min_joints_per_piece: Minimum joints for structural stability
        """
        super().__init__("StructuralValidator")
        self.min_joints_per_piece = min_joints_per_piece

    def validate(
        self, graph: WoodworkingGraph, mode: ValidationMode
    ) -> ValidationResult:
        """Check structural requirements."""
        if graph.node_count() == 0:
            return ValidationSuccess(
                self.name, "Empty graph has no structural requirements"
            )

        issues = []

        # Check minimum joints per piece
        for node_id in graph._graph.nodes():
            # Count connections (both in and out)
            in_degree = graph._graph.in_degree(node_id)
            out_degree = graph._graph.out_degree(node_id)
            total_connections = in_degree + out_degree

            if total_connections < self.min_joints_per_piece:
                severity = ValidationSeverity.WARNING
                if total_connections == 0:
                    severity = ValidationSeverity.ERROR
                elif mode == ValidationMode.STRICT and total_connections == 1:
                    severity = ValidationSeverity.ERROR

                issue = ValidationIssue(
                    severity=severity,
                    validator_name=self.name,
                    message=f"Piece has only {total_connections} connection(s), minimum {self.min_joints_per_piece} recommended",
                    affected_pieces=[node_id],
                    suggestion="Add more connections for structural stability",
                )
                issues.append(issue)

        # TODO: Add more sophisticated structural analysis
        # - Check for cantilevered pieces
        # - Verify load paths
        # - Check triangle/bracing requirements

        if not issues:
            return ValidationSuccess(self.name, "Structural requirements met")

        return ValidationError(self.name, issues)


class AssemblyOrderValidator(GraphValidator):
    """Validates that assembly order is feasible.

    Checks:
    - Assembly order forms a valid sequence
    - No circular dependencies
    - All pieces are reachable in order
    """

    def __init__(self):
        super().__init__("AssemblyOrderValidator")

    def validate(
        self, graph: WoodworkingGraph, mode: ValidationMode
    ) -> ValidationResult:
        """Check assembly order feasibility."""
        # Collect all edges with assembly order
        ordered_edges = []
        for src_id, dst_id, edge_data in graph._graph.edges(data=True):
            joint_data = edge_data.get("data")
            if joint_data and joint_data.assembly_order is not None:
                ordered_edges.append((joint_data.assembly_order, src_id, dst_id))

        if not ordered_edges:
            return ValidationSuccess(self.name, "No assembly order specified")

        issues = []

        # Sort by assembly order
        ordered_edges.sort(key=lambda x: x[0])

        # Check for gaps in sequence
        orders = [edge[0] for edge in ordered_edges]
        expected = list(range(min(orders), max(orders) + 1))
        missing = set(expected) - set(orders)

        if missing:
            severity = (
                ValidationSeverity.WARNING
                if mode == ValidationMode.PERMISSIVE
                else ValidationSeverity.ERROR
            )
            issue = ValidationIssue(
                severity=severity,
                validator_name=self.name,
                message=f"Missing assembly order numbers: {sorted(missing)}",
                affected_pieces=[],
                suggestion="Ensure assembly orders form a continuous sequence",
            )
            issues.append(issue)

        # Check for duplicates
        order_counts = {}
        for order, src, dst in ordered_edges:
            if order not in order_counts:
                order_counts[order] = []
            order_counts[order].append((src, dst))

        for order, edges in order_counts.items():
            if len(edges) > 1:
                affected = []
                for src, dst in edges:
                    affected.extend([src, dst])
                affected = list(set(affected))

                severity = ValidationSeverity.WARNING
                issue = ValidationIssue(
                    severity=severity,
                    validator_name=self.name,
                    message=f"Multiple joints have assembly order {order}",
                    affected_pieces=affected,
                    suggestion="Each assembly step should have a unique order number",
                )
                issues.append(issue)

        # TODO: Check for assembly feasibility
        # - Ensure pieces can be physically assembled in order
        # - Check for blocking/interference

        if not issues:
            return ValidationSuccess(self.name, "Assembly order is valid")

        return ValidationError(self.name, issues)


class GraphValidationSuite:
    """Collection of validators to run on a graph."""

    def __init__(self, validators: Optional[List[GraphValidator]] = None):
        """Initialize with a list of validators.

        Args:
            validators: List of validators to use, or None for defaults
        """
        if validators is None:
            # Default validator set
            self.validators = [
                ConnectivityValidator(),
                CollisionValidator(),
                JointValidator(),
                StructuralValidator(),
                AssemblyOrderValidator(),
            ]
        else:
            self.validators = validators

    def validate(
        self, graph: WoodworkingGraph, mode: ValidationMode = ValidationMode.STRICT
    ) -> ValidationReport:
        """Run all validators on the graph.

        Args:
            graph: The woodworking graph to validate
            mode: Validation strictness mode

        Returns:
            Complete validation report
        """
        report = ValidationReport(mode=mode)

        for validator in self.validators:
            try:
                result = validator.validate(graph, mode)
                report.results.append(result)

                # Log results
                if isinstance(result, ValidationSuccess):
                    logger.info(f"{validator.name}: {result.message}")
                else:
                    logger.warning(
                        f"{validator.name}: Found {result.error_count} errors, "
                        f"{result.warning_count} warnings"
                    )

            except Exception as e:
                # Validator crashed - report as error
                logger.error(f"{validator.name} failed: {str(e)}")
                error_issue = ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    validator_name=validator.name,
                    message=f"Validator crashed: {str(e)}",
                    affected_pieces=[],
                    suggestion="Check validator implementation",
                )
                error_result = ValidationError(validator.name, [error_issue])
                report.results.append(error_result)

        return report


# Convenience functions for common validation tasks


def validate_graph(
    graph: WoodworkingGraph,
    mode: ValidationMode = ValidationMode.STRICT,
    validators: Optional[List[GraphValidator]] = None,
) -> ValidationReport:
    """Validate a woodworking graph with specified validators.

    Args:
        graph: The graph to validate
        mode: Strictness mode
        validators: Custom validator list, or None for defaults

    Returns:
        Validation report
    """
    suite = GraphValidationSuite(validators)
    return suite.validate(graph, mode)


def quick_validate(graph: WoodworkingGraph) -> bool:
    """Quick validation check - returns True if graph is valid.

    Uses strict mode with default validators.

    Args:
        graph: The graph to validate

    Returns:
        True if validation passed, False otherwise
    """
    report = validate_graph(graph, ValidationMode.STRICT)
    return report.passed


def get_validation_summary(report: ValidationReport) -> str:
    """Get a one-line summary of validation results.

    Args:
        report: Validation report

    Returns:
        Summary string
    """
    if report.passed:
        return f"✓ Validation passed ({report.total_warnings} warnings)"
    else:
        return f"✗ Validation failed ({report.total_errors} errors, {report.total_warnings} warnings)"
