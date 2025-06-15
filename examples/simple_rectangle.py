"""Simple example: Create a rectangle frame using nichiyou-daiku.

This is the simplest possible example showing how to:
1. Create 4 lumber pieces
2. Connect them with joints
3. Convert to build123d
"""

from nichiyou_daiku.core.lumber import LumberPiece, LumberType, Face
from nichiyou_daiku.graph.woodworking_graph import WoodworkingGraph
from nichiyou_daiku.connectors.aligned_screw import AlignedScrewJoint
from nichiyou_daiku.rendering.build123d_converter import graph_to_assembly

# Placeholder for old EdgePoint usage
class EdgePoint:
    def __init__(self, face1, face2, position):
        pass


def create_simple_rectangle(
    width: float = 600, 
    height: float = 400
) -> tuple[WoodworkingGraph, dict, dict]:
    """Create a simple rectangle frame from 4 pieces of lumber.
    
    Args:
        width: Rectangle width in mm
        height: Rectangle height in mm
        
    Returns:
        Tuple of (graph, positions, rotations)
    """
    graph = WoodworkingGraph()
    positions = {}
    rotations = {}
    
    # Material thickness (2x4)
    thickness = 38
    lumber_height = 89
    
    # Create 4 pieces
    # Top and bottom pieces run horizontally (width)
    top = LumberPiece("top", LumberType.LUMBER_2X4, width)
    bottom = LumberPiece("bottom", LumberType.LUMBER_2X4, width)
    
    # Left and right pieces run vertically (height)
    # Make them shorter to fit inside top/bottom
    left = LumberPiece("left", LumberType.LUMBER_2X4, height - 2 * lumber_height)
    right = LumberPiece("right", LumberType.LUMBER_2X4, height - 2 * lumber_height)
    
    # Add all pieces to graph
    for piece in [top, bottom, left, right]:
        graph.add_lumber_piece(piece)
    
    # Position the pieces to form a rectangle
    # Top piece at the top
    positions["top"] = (0, 0, height - lumber_height)
    rotations["top"] = (0, 90, 0)  # Rotate to lay flat
    
    # Bottom piece at the bottom
    positions["bottom"] = (0, 0, 0)
    rotations["bottom"] = (0, 90, 0)  # Rotate to lay flat
    
    # Left piece on the left side
    positions["left"] = (0, 0, lumber_height)
    rotations["left"] = (0, 0, 0)  # Vertical orientation
    
    # Right piece on the right side
    positions["right"] = (width - thickness, 0, lumber_height)
    rotations["right"] = (0, 0, 0)  # Vertical orientation
    
    # Add joints to connect the pieces
    # Top-left corner: Connect top to left
    top_left_joint = AlignedScrewJoint(
        src_face=Face.LEFT,
        dst_face=Face.TOP,
        src_edge_point=EdgePoint(Face.LEFT, Face.BOTTOM, 0.1),
        dst_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.95)
    )
    graph.add_joint("top", "left", top_left_joint)
    
    # Top-right corner: Connect top to right
    top_right_joint = AlignedScrewJoint(
        src_face=Face.RIGHT,
        dst_face=Face.TOP,
        src_edge_point=EdgePoint(Face.RIGHT, Face.BOTTOM, 0.9),
        dst_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.95)
    )
    graph.add_joint("top", "right", top_right_joint)
    
    # Bottom-left corner: Connect bottom to left
    bottom_left_joint = AlignedScrewJoint(
        src_face=Face.LEFT,
        dst_face=Face.BOTTOM,
        src_edge_point=EdgePoint(Face.LEFT, Face.TOP, 0.1),
        dst_edge_point=EdgePoint(Face.BOTTOM, Face.RIGHT, 0.05)
    )
    graph.add_joint("bottom", "left", bottom_left_joint)
    
    # Bottom-right corner: Connect bottom to right
    bottom_right_joint = AlignedScrewJoint(
        src_face=Face.RIGHT,
        dst_face=Face.BOTTOM,
        src_edge_point=EdgePoint(Face.RIGHT, Face.TOP, 0.9),
        dst_edge_point=EdgePoint(Face.BOTTOM, Face.RIGHT, 0.05)
    )
    graph.add_joint("bottom", "right", bottom_right_joint)
    
    return graph, positions, rotations


def create_simple_box(
    width: float = 400,
    length: float = 600,
    height: float = 300
) -> tuple[WoodworkingGraph, dict, dict]:
    """Create a simple box frame (no top/bottom panels).
    
    Args:
        width: Box width in mm
        length: Box length in mm  
        height: Box height in mm
        
    Returns:
        Tuple of (graph, positions, rotations)
    """
    graph = WoodworkingGraph()
    positions = {}
    rotations = {}
    
    thickness = 38
    
    # Create 12 pieces for a box frame (4 vertical, 4 top horizontal, 4 bottom horizontal)
    # Vertical posts
    for i in range(4):
        post_id = f"post_{i}"
        post = LumberPiece(post_id, LumberType.LUMBER_2X4, height)
        graph.add_lumber_piece(post)
        
        # Position at corners
        x = (i % 2) * (length - thickness)
        y = (i // 2) * (width - thickness)
        positions[post_id] = (x, y, 0)
    
    # Top rails
    top_front = LumberPiece("top_front", LumberType.LUMBER_2X4, length)
    top_back = LumberPiece("top_back", LumberType.LUMBER_2X4, length)
    top_left = LumberPiece("top_left", LumberType.LUMBER_2X4, width - 2 * thickness)
    top_right = LumberPiece("top_right", LumberType.LUMBER_2X4, width - 2 * thickness)
    
    for piece in [top_front, top_back, top_left, top_right]:
        graph.add_lumber_piece(piece)
    
    # Position top rails
    positions["top_front"] = (0, 0, height - 89)
    rotations["top_front"] = (0, 90, 0)
    
    positions["top_back"] = (0, width - thickness, height - 89)
    rotations["top_back"] = (0, 90, 0)
    
    positions["top_left"] = (0, thickness, height - 89)
    rotations["top_left"] = (90, 90, 0)
    
    positions["top_right"] = (length - thickness, thickness, height - 89)
    rotations["top_right"] = (90, 90, 0)
    
    # Bottom rails
    bottom_front = LumberPiece("bottom_front", LumberType.LUMBER_2X4, length)
    bottom_back = LumberPiece("bottom_back", LumberType.LUMBER_2X4, length)
    bottom_left = LumberPiece("bottom_left", LumberType.LUMBER_2X4, width - 2 * thickness)
    bottom_right = LumberPiece("bottom_right", LumberType.LUMBER_2X4, width - 2 * thickness)
    
    for piece in [bottom_front, bottom_back, bottom_left, bottom_right]:
        graph.add_lumber_piece(piece)
    
    # Position bottom rails
    positions["bottom_front"] = (0, 0, 0)
    rotations["bottom_front"] = (0, 90, 0)
    
    positions["bottom_back"] = (0, width - thickness, 0)
    rotations["bottom_back"] = (0, 90, 0)
    
    positions["bottom_left"] = (0, thickness, 0)
    rotations["bottom_left"] = (90, 90, 0)
    
    positions["bottom_right"] = (length - thickness, thickness, 0)
    rotations["bottom_right"] = (90, 90, 0)
    
    # Add some example joints (connecting posts to rails)
    # Connect post_0 to bottom_front
    joint1 = AlignedScrewJoint(
        src_face=Face.FRONT,
        dst_face=Face.BOTTOM,
        src_edge_point=EdgePoint(Face.FRONT, Face.LEFT, 0.1),
        dst_edge_point=EdgePoint(Face.BOTTOM, Face.LEFT, 0.05)
    )
    graph.add_joint("post_0", "bottom_front", joint1)
    
    # Connect post_0 to bottom_left
    joint2 = AlignedScrewJoint(
        src_face=Face.LEFT,
        dst_face=Face.BOTTOM,
        src_edge_point=EdgePoint(Face.LEFT, Face.FRONT, 0.1),
        dst_edge_point=EdgePoint(Face.BOTTOM, Face.FRONT, 0.05)
    )
    graph.add_joint("post_0", "bottom_left", joint2)
    
    return graph, positions, rotations


def main():
    """Demonstrate simple furniture examples."""
    print("Creating simple furniture examples...")
    print("=" * 60)
    
    # Example 1: Simple Rectangle Frame
    print("\n1. Simple Rectangle Frame")
    print("-" * 30)
    graph1, positions1, rotations1 = create_simple_rectangle(800, 500)
    print(f"Created rectangle with {graph1.node_count()} pieces")
    print(f"Number of joints: {graph1.edge_count()}")
    
    # Convert to build123d
    assembly1 = graph_to_assembly(graph1, positions1, rotations1)
    if assembly1:
        print("Successfully converted to build123d assembly")
    
    # Example 2: Simple Box Frame
    print("\n2. Simple Box Frame")
    print("-" * 30)
    graph2, positions2, rotations2 = create_simple_box(400, 600, 350)
    print(f"Created box frame with {graph2.node_count()} pieces")
    print(f"Number of joints: {graph2.edge_count()}")
    
    # Convert to build123d
    assembly2 = graph_to_assembly(graph2, positions2, rotations2)
    if assembly2:
        print("Successfully converted to build123d assembly")
    
    print("\n" + "=" * 60)
    print("These simple examples demonstrate:")
    print("- Basic lumber piece creation")
    print("- Positioning and rotation of pieces")
    print("- Joint connections between pieces")
    print("- Graph to build123d conversion")
    
    print("\nTo visualize:")
    print("  from build123d import show")
    print("  show(assembly1)  # Rectangle frame")
    print("  show(assembly2)  # Box frame")
    
    return assembly1, assembly2


if __name__ == "__main__":
    try:
        assembly1, assembly2 = main()
    except ImportError as e:
        print(f"\nNote: {e}")
        print("build123d requires a graphical environment with OpenGL support.")

    from ocp_vscode import show
    show(assembly1)  # Show rectangle frame