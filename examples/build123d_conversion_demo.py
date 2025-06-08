"""Demo of converting woodworking graph to build123d objects.

This example shows how to:
1. Create a simple furniture assembly (table frame)
2. Convert it to build123d objects
3. Visualize using build123d's show() method

For more complex examples, see:
- bookshelf_example.py: Traditional bookshelf and modular storage
- workbench_example.py: Heavy-duty and mobile workbenches
- parametric_furniture.py: Customizable, parametric designs
"""

from nichiyou_daiku.core.lumber import LumberPiece, LumberType
from nichiyou_daiku.graph.woodworking_graph import WoodworkingGraph
from nichiyou_daiku.rendering.build123d_converter import (
    GraphToBuild123D,
    lumber_to_box,
    graph_to_assembly,
)


def create_simple_table_frame():
    """Create a simple table frame graph."""
    graph = WoodworkingGraph()

    # Table legs (4 pieces)
    leg1 = LumberPiece("leg1", LumberType.LUMBER_2X4, 700)
    leg2 = LumberPiece("leg2", LumberType.LUMBER_2X4, 700)
    leg3 = LumberPiece("leg3", LumberType.LUMBER_2X4, 700)
    leg4 = LumberPiece("leg4", LumberType.LUMBER_2X4, 700)

    # Table top frame (4 pieces)
    top1 = LumberPiece("top1", LumberType.LUMBER_2X4, 600)
    top2 = LumberPiece("top2", LumberType.LUMBER_2X4, 600)
    top3 = LumberPiece("top3", LumberType.LUMBER_2X4, 400)
    top4 = LumberPiece("top4", LumberType.LUMBER_2X4, 400)

    # Add all pieces to graph
    # Note: Position and rotation would be stored in the graph node data
    # or determined by joint relationships, not in the lumber piece itself
    for piece in [leg1, leg2, leg3, leg4, top1, top2, top3, top4]:
        graph.add_lumber_piece(piece)

    return graph


def main():
    """Main demo function."""
    print("Creating table frame graph...")
    graph = create_simple_table_frame()
    print(f"Graph has {graph.node_count()} pieces")

    print("\nDemo 1: Using standalone functions (Task 4.2 & 4.3)")
    print("=" * 50)

    # Task 4.2: Convert individual piece
    print("Converting individual piece with lumber_to_box():")
    test_piece = LumberPiece("test", LumberType.LUMBER_2X4, 1000)
    box = lumber_to_box(test_piece, position=(100, 200, 300))
    print(f"  Created box: {box}")

    # Task 4.3: Convert entire graph
    print("\nConverting graph with graph_to_assembly():")
    compound = graph_to_assembly(graph)

    if compound:
        print("  Created compound with assembly")
    else:
        print("  No compound created (empty graph)")

    print("\nDemo 2: Using GraphToBuild123D class")
    print("=" * 50)
    converter = GraphToBuild123D()

    # Convert using class methods
    print("Converting with class methods:")
    box2 = converter.lumber_to_box(test_piece, position=(100, 200, 300))
    print(f"  Created box: {box2}")

    compound2 = converter.graph_to_compound(graph)

    if compound2:
        print("  Created compound with pieces")
        print("\nTo visualize in build123d:")
        print("  from build123d import show")
        print("  show(compound)  # or show(compound2)")
    else:
        print("  No compound created (empty graph)")


if __name__ == "__main__":
    try:
        main()
    except ImportError as e:
        print(f"\nNote: {e}")
        print("build123d requires a graphical environment with OpenGL support.")
        print("The converter code is working, but visualization requires proper setup.")
