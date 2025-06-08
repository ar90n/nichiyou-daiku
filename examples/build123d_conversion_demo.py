"""Demo of converting woodworking graph to build123d objects.

This example shows how to:
1. Create a simple furniture assembly (table frame)
2. Convert it to build123d objects
3. Visualize using build123d's show() method
"""

from nichiyou_daiku.core.lumber import LumberPiece, LumberType
from nichiyou_daiku.graph.woodworking_graph import WoodworkingGraph
from nichiyou_daiku.rendering.build123d_converter import GraphToBuild123D


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

    print("\nConverting to build123d...")
    converter = GraphToBuild123D()

    # Convert individual pieces
    print("Converting individual pieces:")
    test_piece = LumberPiece("test", LumberType.LUMBER_2X4, 1000)
    box = converter.lumber_to_box(test_piece, position=(100, 200, 300))
    print(f"  Created box: {box}")

    # Convert entire graph
    print("\nConverting entire graph to compound:")
    compound = converter.graph_to_compound(graph)

    if compound:
        print(f"  Created compound with pieces")
        print("\nTo visualize in build123d:")
        print("  from build123d import show")
        print("  show(compound)")
    else:
        print("  No compound created (empty graph)")


if __name__ == "__main__":
    try:
        main()
    except ImportError as e:
        print(f"\nNote: {e}")
        print("build123d requires a graphical environment with OpenGL support.")
        print("The converter code is working, but visualization requires proper setup.")
