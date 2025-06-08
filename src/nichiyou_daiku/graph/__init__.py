"""Graph-based assembly management for woodworking projects."""

from nichiyou_daiku.graph.woodworking_graph import (
    WoodworkingGraph,
    NodeData,
    EdgeData,
    create_lumber_node,
    create_joint_edge,
    calculate_world_position,
    calculate_piece_origin_position,
)

from nichiyou_daiku.graph.validation import (
    ValidationMode,
    ValidationSeverity,
    ValidationIssue,
    ValidationSuccess,
    ValidationError,
    ValidationReport,
    GraphValidator,
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

__all__ = [
    # Graph classes
    "WoodworkingGraph",
    "NodeData",
    "EdgeData",
    "create_lumber_node",
    "create_joint_edge",
    "calculate_world_position",
    "calculate_piece_origin_position",
    # Validation enums and data classes
    "ValidationMode",
    "ValidationSeverity",
    "ValidationIssue",
    "ValidationSuccess",
    "ValidationError",
    "ValidationReport",
    # Validators
    "GraphValidator",
    "ConnectivityValidator",
    "CollisionValidator",
    "JointValidator",
    "StructuralValidator",
    "AssemblyOrderValidator",
    "GraphValidationSuite",
    # Convenience functions
    "validate_graph",
    "quick_validate",
    "get_validation_summary",
]
