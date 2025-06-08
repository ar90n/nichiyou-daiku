"""Example: Create a bookshelf using nichiyou-daiku.

This example demonstrates:
1. Building a complex furniture piece (bookshelf)
2. Using the graph structure with positions
3. Converting to build123d for visualization
"""

from nichiyou_daiku.core.lumber import LumberPiece, LumberType
from nichiyou_daiku.graph.woodworking_graph import WoodworkingGraph
from nichiyou_daiku.rendering.build123d_converter import graph_to_assembly
from nichiyou_daiku.connectors.aligned_screw import AlignedScrewJoint, ScrewSpec
from nichiyou_daiku.core.geometry import Face, EdgePoint


def create_bookshelf(
    width: float = 800,
    height: float = 1800,
    depth: float = 300,
    num_shelves: int = 5,
) -> tuple[WoodworkingGraph, dict, dict]:
    """Create a bookshelf design.

    Args:
        width: Overall width in mm
        height: Overall height in mm
        depth: Overall depth in mm
        num_shelves: Number of shelves (including top and bottom)

    Returns:
        Tuple of (graph, positions, rotations)
    """
    graph = WoodworkingGraph()
    positions = {}
    rotations = {}

    # Material thickness
    thickness = 38  # 2x lumber thickness

    # Calculate shelf spacing
    shelf_spacing = (height - thickness) / (num_shelves - 1)

    # Create vertical supports (sides)
    left_support = LumberPiece("left_support", LumberType.LUMBER_2X16, height)
    right_support = LumberPiece("right_support", LumberType.LUMBER_2X16, height)

    graph.add_lumber_piece(left_support)
    graph.add_lumber_piece(right_support)

    # Position vertical supports
    positions["left_support"] = (0, 0, 0)
    positions["right_support"] = (width - thickness, 0, 0)

    # Create shelves
    shelves = []
    for i in range(num_shelves):
        shelf_id = f"shelf_{i}"
        shelf = LumberPiece(shelf_id, LumberType.LUMBER_2X16, width)
        graph.add_lumber_piece(shelf)
        shelves.append((shelf_id, shelf))

        # Position shelf
        z_position = i * shelf_spacing
        positions[shelf_id] = (0, 0, z_position)
        # Rotate shelf to lay flat
        rotations[shelf_id] = (0, 90, 0)

    # Add back panel (optional - using multiple 1x8 boards)
    back_board_width = 184  # 1x8 actual width
    num_back_boards = int(width / back_board_width) + 1

    for i in range(num_back_boards):
        back_id = f"back_board_{i}"
        back_board = LumberPiece(back_id, LumberType.LUMBER_1X8, height)
        graph.add_lumber_piece(back_board)

        # Position back boards
        x_position = i * back_board_width
        positions[back_id] = (x_position, depth - 19, 0)  # 19mm is 1x thickness

    # Add joints between components
    screw_spec = ScrewSpec(diameter=4.0, length=65.0)

    # Connect shelves to sides
    for shelf_id, shelf in shelves:
        # Left side connections
        left_joint = AlignedScrewJoint(
            lumber1_id="left_support",
            lumber2_id=shelf_id,
            face1=Face.RIGHT,
            face2=Face.LEFT,
            edge_point1=EdgePoint(offset1=0.5, offset2=0.5),
            edge_point2=EdgePoint(offset1=0.1, offset2=0.5),
            screw_specs=[screw_spec, screw_spec],  # Two screws per connection
            screw_direction=(1, 0, 0),
        )
        graph.add_joint(left_joint)

        # Right side connections
        right_joint = AlignedScrewJoint(
            lumber1_id="right_support",
            lumber2_id=shelf_id,
            face1=Face.LEFT,
            face2=Face.RIGHT,
            edge_point1=EdgePoint(offset1=0.5, offset2=0.5),
            edge_point2=EdgePoint(offset1=0.9, offset2=0.5),
            screw_specs=[screw_spec, screw_spec],
            screw_direction=(-1, 0, 0),
        )
        graph.add_joint(right_joint)

    return graph, positions, rotations


def create_modular_shelf_unit(
    modules_x: int = 3,
    modules_y: int = 4,
    module_size: float = 400,
) -> tuple[WoodworkingGraph, dict, dict]:
    """Create a modular shelf unit with grid pattern.

    Args:
        modules_x: Number of modules horizontally
        modules_y: Number of modules vertically
        module_size: Size of each module in mm

    Returns:
        Tuple of (graph, positions, rotations)
    """
    graph = WoodworkingGraph()
    positions = {}
    rotations = {}

    thickness = 38  # 2x lumber

    # Create vertical dividers
    for i in range(modules_x + 1):
        divider_id = f"v_divider_{i}"
        divider = LumberPiece(
            divider_id, LumberType.LUMBER_2X8, modules_y * module_size
        )
        graph.add_lumber_piece(divider)

        x_position = i * module_size
        positions[divider_id] = (x_position, 0, 0)

    # Create horizontal shelves
    for j in range(modules_y + 1):
        shelf_id = f"h_shelf_{j}"
        shelf = LumberPiece(
            shelf_id, LumberType.LUMBER_2X8, modules_x * module_size + thickness
        )
        graph.add_lumber_piece(shelf)

        z_position = j * module_size
        positions[shelf_id] = (0, 0, z_position)
        rotations[shelf_id] = (0, 90, 0)

    # Add diagonal braces for stability (optional)
    if modules_x >= 2 and modules_y >= 2:
        # Add X-brace in back
        brace_length = (module_size**2 + module_size**2) ** 0.5

        brace1 = LumberPiece("brace_1", LumberType.LUMBER_1X4, brace_length)
        brace2 = LumberPiece("brace_2", LumberType.LUMBER_1X4, brace_length)

        graph.add_lumber_piece(brace1)
        graph.add_lumber_piece(brace2)

        # Position braces diagonally
        positions["brace_1"] = (module_size, 200, module_size)
        rotations["brace_1"] = (0, 45, 0)

        positions["brace_2"] = (module_size, 200, 0)
        rotations["brace_2"] = (0, -45, 0)

    return graph, positions, rotations


def main():
    """Demonstrate complex furniture examples."""
    print("Creating complex furniture examples...")
    print("=" * 60)

    # Example 1: Traditional Bookshelf
    print("\n1. Traditional Bookshelf")
    print("-" * 30)
    graph1, positions1, rotations1 = create_bookshelf(
        width=900, height=1800, depth=300, num_shelves=6
    )
    print(f"Created bookshelf with {graph1.node_count()} pieces")
    print(f"Number of joints: {graph1.edge_count()}")

    # Convert to build123d
    assembly1 = graph_to_assembly(graph1, positions1, rotations1)
    if assembly1:
        print("Successfully converted to build123d assembly")

    # Example 2: Modular Shelf Unit
    print("\n2. Modular Shelf Unit")
    print("-" * 30)
    graph2, positions2, rotations2 = create_modular_shelf_unit(
        modules_x=4, modules_y=4, module_size=350
    )
    print(f"Created modular unit with {graph2.node_count()} pieces")

    # Convert to build123d
    assembly2 = graph_to_assembly(graph2, positions2, rotations2)
    if assembly2:
        print("Successfully converted to build123d assembly")

    # Print visualization instructions
    print("\n" + "=" * 60)
    print("To visualize these designs in build123d:")
    print("1. Run this script in an environment with build123d")
    print("2. Add the following code:")
    print("   from build123d import show")
    print("   show(assembly1)  # For bookshelf")
    print("   show(assembly2)  # For modular unit")

    return assembly1, assembly2


if __name__ == "__main__":
    try:
        assembly1, assembly2 = main()
    except ImportError as e:
        print(f"\nNote: {e}")
        print("build123d requires a graphical environment with OpenGL support.")
        print(
            "The graph creation and conversion code works, but visualization requires proper setup."
        )
