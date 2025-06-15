"""Simple L-angle connection example using nichiyou-daiku.

This example demonstrates the most basic connection:
1. Two lumber pieces forming an L shape
2. Proper joint configuration
3. Correct positioning for the connection
"""

from nichiyou_daiku.core.lumber import LumberPiece, LumberType, Face
from nichiyou_daiku.graph.woodworking_graph import WoodworkingGraph
from nichiyou_daiku.connectors.general import GeneralJoint, JointLocation, JointPose
from nichiyou_daiku.rendering.build123d_converter import graph_to_assembly


def create_l_angle_connection(
    vertical_length: float = 600,
    horizontal_length: float = 400,
) -> tuple[WoodworkingGraph, dict, dict]:
    """Create a simple L-angle connection with two lumber pieces.
    
    Args:
        vertical_length: Length of the vertical piece in mm
        horizontal_length: Length of the horizontal piece in mm
        
    Returns:
        Tuple of (graph, positions, rotations)
    """
    graph = WoodworkingGraph()
    
    # Create two lumber pieces
    vertical = LumberPiece("vertical", LumberType.LUMBER_2X4, vertical_length)
    horizontal = LumberPiece("horizontal", LumberType.LUMBER_2X4, horizontal_length)
    
    # Create joint connecting vertical's TOP face to horizontal's LEFT face
    joint = GeneralJoint(
        base_loc= JointLocation(Face.LEFT, 300.0 - horizontal.get_dimensions()[1] / 2),
        target_loc= JointLocation(Face.TOP, 0.0),
        target_pose= JointPose(Face.FRONT, Face.LEFT)
    )
    
    # Add pieces to graph
    graph.add_lumber_piece(vertical)
    graph.add_lumber_piece(horizontal)
    # Add joint from vertical to horizontal
    graph.add_joint(vertical.id, horizontal.id, joint)
    
    return graph

def main():
    """Demonstrate L-angle connections."""
    print("Creating L-angle connection examples...")
    print("=" * 60)
    
    # Example 1: Basic L-angle
    print("\n1. Basic L-Angle Connection")
    print("-" * 30)
    graph1 = create_l_angle_connection()
    print(f"Created L-angle with {graph1.node_count()} pieces")
    print(f"Number of joints: {graph1.edge_count()}")
    
    # Convert to build123d
    assembly1 = graph_to_assembly(graph1)
    if assembly1:
        print("Successfully converted to build123d assembly")
    
    return assembly1


if __name__ == "__main__":
    try:
        assembly1= main()
    except ImportError as e:
        print(f"\nNote: {e}")
        print("build123d requires a graphical environment with OpenGL support.")

    from ocp_vscode import show
    show(assembly1)  # Show basic L-angle