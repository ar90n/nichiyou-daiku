#!/usr/bin/env python3
"""Demonstration of the graph validation system."""

from nichiyou_daiku.core.lumber import LumberPiece, LumberType, Face
from nichiyou_daiku.core.geometry import EdgePoint
from nichiyou_daiku.connectors.aligned_screw import AlignedScrewJoint
from nichiyou_daiku.graph import (
    WoodworkingGraph,
    ValidationMode,
    validate_graph,
    quick_validate,
)


def create_invalid_graph():
    """Create a graph with various validation issues."""
    graph = WoodworkingGraph()

    # Add some connected pieces
    beam1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
    beam2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)
    beam3 = LumberPiece("beam3", LumberType.LUMBER_2X4, 1000.0)

    # Add a floating piece
    floating = LumberPiece("floating", LumberType.LUMBER_2X4, 500.0)

    graph.add_lumber_piece(beam1)
    graph.add_lumber_piece(beam2)
    graph.add_lumber_piece(beam3)
    graph.add_lumber_piece(floating)

    # Connect only some pieces
    joint = AlignedScrewJoint(
        src_face=Face.TOP,
        dst_face=Face.TOP,
        src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
        dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
    )

    graph.add_joint("beam1", "beam2", joint)

    # Add a joint with invalid edge point
    invalid_joint = AlignedScrewJoint(
        src_face=Face.TOP,
        dst_face=Face.BOTTOM,
        src_edge_point=EdgePoint(Face.BOTTOM, Face.RIGHT, 0.5),  # Wrong face!
        dst_edge_point=EdgePoint(Face.BOTTOM, Face.LEFT, 0.5),
    )

    graph.add_joint("beam2", "beam3", invalid_joint)

    return graph


def create_valid_graph():
    """Create a properly validated graph."""
    graph = WoodworkingGraph()

    # Create a simple frame structure
    top = LumberPiece("top", LumberType.LUMBER_2X4, 1000.0)
    bottom = LumberPiece("bottom", LumberType.LUMBER_2X4, 1000.0)
    left = LumberPiece("left", LumberType.LUMBER_2X4, 600.0)
    right = LumberPiece("right", LumberType.LUMBER_2X4, 600.0)

    graph.add_lumber_piece(top)
    graph.add_lumber_piece(bottom)
    graph.add_lumber_piece(left)
    graph.add_lumber_piece(right)

    # Connect them in a rectangle
    corner_joint = AlignedScrewJoint(
        src_face=Face.FRONT,
        dst_face=Face.BACK,
        src_edge_point=EdgePoint(Face.FRONT, Face.TOP, 0.0),
        dst_edge_point=EdgePoint(Face.BACK, Face.TOP, 0.0),
    )

    # Top-left connection
    graph.add_joint("left", "top", corner_joint, assembly_order=1)
    # Top-right connection
    graph.add_joint("top", "right", corner_joint, assembly_order=2)
    # Right-bottom connection
    graph.add_joint("right", "bottom", corner_joint, assembly_order=3)
    # Bottom-left connection
    graph.add_joint("bottom", "left", corner_joint, assembly_order=4)

    return graph


def main():
    """Run validation demonstrations."""
    print("Graph Validation System Demo")
    print("=" * 40)

    # Demo 1: Invalid graph with strict validation
    print("\n1. Invalid Graph - Strict Mode")
    print("-" * 30)

    invalid_graph = create_invalid_graph()
    report = validate_graph(invalid_graph, ValidationMode.STRICT)

    print(report.to_string())

    # Demo 2: Same graph with permissive validation
    print("\n\n2. Invalid Graph - Permissive Mode")
    print("-" * 30)

    report = validate_graph(invalid_graph, ValidationMode.PERMISSIVE)
    print(report.to_string())

    # Demo 3: Valid graph
    print("\n\n3. Valid Graph")
    print("-" * 30)

    valid_graph = create_valid_graph()
    report = validate_graph(valid_graph, ValidationMode.STRICT)
    print(report.to_string())

    # Demo 4: Quick validation
    print("\n\n4. Quick Validation")
    print("-" * 30)

    print(f"Invalid graph quick check: {quick_validate(invalid_graph)}")
    print(f"Valid graph quick check: {quick_validate(valid_graph)}")


if __name__ == "__main__":
    main()
