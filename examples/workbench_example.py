"""Example: Create a sturdy workbench using nichiyou-daiku.

This example demonstrates:
1. Building a heavy-duty workbench
2. Complex joinery with multiple connection points
3. Using different lumber sizes for different components
"""

from nichiyou_daiku.core.lumber import LumberPiece, LumberType
from nichiyou_daiku.graph.woodworking_graph import WoodworkingGraph
from nichiyou_daiku.rendering.build123d_converter import graph_to_assembly
from nichiyou_daiku.connectors.aligned_screw import AlignedScrewJoint, ScrewSpec
from nichiyou_daiku.core.geometry import Face, EdgePoint


def create_workbench(
    length: float = 1800,
    width: float = 600,
    height: float = 900,
    with_shelf: bool = True,
) -> tuple[WoodworkingGraph, dict, dict]:
    """Create a sturdy workbench design.

    Args:
        length: Workbench length in mm
        width: Workbench width in mm
        height: Workbench height in mm
        with_shelf: Whether to include a lower shelf

    Returns:
        Tuple of (graph, positions, rotations)
    """
    graph = WoodworkingGraph()
    positions = {}
    rotations = {}

    # Material specs
    leg_thickness = 89  # 2x4 height when vertical
    leg_width = 38  # 2x4 width
    top_thickness = 38  # 2x lumber laid flat

    # Create legs (using doubled 2x4s for strength)
    legs = []
    leg_positions = [
        (leg_width, leg_width, 0),  # Front left
        (length - leg_width * 2, leg_width, 0),  # Front right
        (leg_width, width - leg_width * 2, 0),  # Back left
        (length - leg_width * 2, width - leg_width * 2, 0),  # Back right
    ]

    for i, pos in enumerate(leg_positions):
        # Each leg is made of two 2x4s
        for j in range(2):
            leg_id = f"leg_{i}_{j}"
            leg = LumberPiece(leg_id, LumberType.LUMBER_2X4, height)
            graph.add_lumber_piece(leg)
            legs.append(leg_id)

            # Position legs side by side
            x, y, z = pos
            if j == 1:
                x += leg_width
            positions[leg_id] = (x, y, z)

    # Create top frame (aprons)
    # Front and back aprons
    front_apron = LumberPiece(
        "front_apron", LumberType.LUMBER_2X4, length - leg_width * 4
    )
    back_apron = LumberPiece(
        "back_apron", LumberType.LUMBER_2X4, length - leg_width * 4
    )
    graph.add_lumber_piece(front_apron)
    graph.add_lumber_piece(back_apron)

    positions["front_apron"] = (leg_width * 2, 0, height - leg_thickness)
    rotations["front_apron"] = (0, 90, 0)

    positions["back_apron"] = (leg_width * 2, width - leg_width, height - leg_thickness)
    rotations["back_apron"] = (0, 90, 0)

    # Side aprons
    left_apron = LumberPiece("left_apron", LumberType.LUMBER_2X4, width - leg_width * 2)
    right_apron = LumberPiece(
        "right_apron", LumberType.LUMBER_2X4, width - leg_width * 2
    )
    graph.add_lumber_piece(left_apron)
    graph.add_lumber_piece(right_apron)

    positions["left_apron"] = (0, leg_width, height - leg_thickness)
    rotations["left_apron"] = (90, 90, 0)

    positions["right_apron"] = (length - leg_width, leg_width, height - leg_thickness)
    rotations["right_apron"] = (90, 90, 0)

    # Create workbench top (multiple 2x8s for a thick, sturdy surface)
    num_top_boards = int(width / 184) + 1  # 184mm is 2x8 actual width
    for i in range(num_top_boards):
        top_id = f"top_board_{i}"
        top_board = LumberPiece(top_id, LumberType.LUMBER_2X8, length)
        graph.add_lumber_piece(top_board)

        # Position top boards
        y_position = i * 184
        positions[top_id] = (0, y_position, height)
        rotations[top_id] = (0, 0, 0)  # Boards laid flat

    # Add lower shelf if requested
    if with_shelf:
        shelf_height = 300  # Shelf 300mm from ground

        # Shelf supports (stretchers)
        front_stretcher = LumberPiece(
            "front_stretcher", LumberType.LUMBER_2X4, length - leg_width * 4
        )
        back_stretcher = LumberPiece(
            "back_stretcher", LumberType.LUMBER_2X4, length - leg_width * 4
        )
        graph.add_lumber_piece(front_stretcher)
        graph.add_lumber_piece(back_stretcher)

        positions["front_stretcher"] = (leg_width * 2, leg_width, shelf_height)
        rotations["front_stretcher"] = (0, 90, 0)

        positions["back_stretcher"] = (
            leg_width * 2,
            width - leg_width * 2,
            shelf_height,
        )
        rotations["back_stretcher"] = (0, 90, 0)

        # Side stretchers
        left_stretcher = LumberPiece(
            "left_stretcher", LumberType.LUMBER_2X4, width - leg_width * 4
        )
        right_stretcher = LumberPiece(
            "right_stretcher", LumberType.LUMBER_2X4, width - leg_width * 4
        )
        graph.add_lumber_piece(left_stretcher)
        graph.add_lumber_piece(right_stretcher)

        positions["left_stretcher"] = (leg_width, leg_width * 2, shelf_height)
        rotations["left_stretcher"] = (90, 90, 0)

        positions["right_stretcher"] = (
            length - leg_width * 2,
            leg_width * 2,
            shelf_height,
        )
        rotations["right_stretcher"] = (90, 90, 0)

        # Shelf boards (using 1x8s for lighter weight)
        num_shelf_boards = int(width / 184) + 1
        for i in range(num_shelf_boards):
            shelf_id = f"shelf_board_{i}"
            shelf_board = LumberPiece(
                shelf_id, LumberType.LUMBER_1X8, length - leg_width * 4
            )
            graph.add_lumber_piece(shelf_board)

            y_position = leg_width * 2 + i * 184
            positions[shelf_id] = (
                leg_width * 2,
                y_position,
                shelf_height + top_thickness,
            )
            rotations[shelf_id] = (0, 0, 0)

    # Add diagonal braces for extra stability
    # Front diagonal brace
    brace_length = ((height - leg_thickness) ** 2 + (length / 3) ** 2) ** 0.5
    front_brace = LumberPiece("front_brace", LumberType.LUMBER_2X4, brace_length)
    graph.add_lumber_piece(front_brace)

    positions["front_brace"] = (length / 3, 0, height / 3)
    rotations["front_brace"] = (0, 30, 0)  # Angled brace

    # Add joints (simplified - in reality would have many more)
    screw_spec = ScrewSpec(diameter=5.0, length=80.0)  # Heavy duty screws

    # Connect aprons to legs
    for i in range(4):
        leg_base = f"leg_{i}_0"

        # Connect to appropriate apron based on position
        if i < 2:  # Front legs
            graph.add_joint(
                AlignedScrewJoint(
                    lumber1_id=leg_base,
                    lumber2_id="front_apron",
                    face1=Face.BACK,
                    face2=Face.FRONT,
                    edge_point1=EdgePoint(0.9, 0.5),
                    edge_point2=EdgePoint(0.1 + i * 0.8, 0.5),
                    screw_specs=[screw_spec, screw_spec],
                    screw_direction=(0, 1, 0),
                )
            )

    return graph, positions, rotations


def create_mobile_workbench(
    length: float = 1200,
    width: float = 600,
    height: float = 850,
) -> tuple[WoodworkingGraph, dict, dict]:
    """Create a mobile workbench with casters and tool storage.

    Args:
        length: Workbench length in mm
        width: Workbench width in mm
        height: Workbench height in mm

    Returns:
        Tuple of (graph, positions, rotations)
    """
    graph = WoodworkingGraph()
    positions = {}
    rotations = {}

    # Base frame (heavier lumber for stability)
    thickness = 38

    # Create frame using 2x8s for extra strength
    frame_pieces = [
        ("frame_front", LumberType.LUMBER_2X8, length),
        ("frame_back", LumberType.LUMBER_2X8, length),
        ("frame_left", LumberType.LUMBER_2X8, width),
        ("frame_right", LumberType.LUMBER_2X8, width),
    ]

    for piece_id, lumber_type, piece_length in frame_pieces:
        piece = LumberPiece(piece_id, lumber_type, piece_length)
        graph.add_lumber_piece(piece)

    # Position frame pieces
    positions["frame_front"] = (0, 0, height)
    rotations["frame_front"] = (0, 90, 0)

    positions["frame_back"] = (0, width - thickness, height)
    rotations["frame_back"] = (0, 90, 0)

    positions["frame_left"] = (0, 0, height)
    rotations["frame_left"] = (90, 90, 0)

    positions["frame_right"] = (length - thickness, 0, height)
    rotations["frame_right"] = (90, 90, 0)

    # Add pegboard back for tool storage
    pegboard_height = 400
    back_panel = LumberPiece("pegboard_frame", LumberType.LUMBER_1X4, pegboard_height)
    graph.add_lumber_piece(back_panel)

    positions["pegboard_frame"] = (length / 4, width - 19, height + thickness)

    # Add drawer frame underneath
    drawer_height = 150
    drawer_rails = [
        ("drawer_rail_left", 0, 0, height - drawer_height),
        ("drawer_rail_right", length - thickness, 0, height - drawer_height),
    ]

    for rail_id, x, y, z in drawer_rails:
        rail = LumberPiece(rail_id, LumberType.LUMBER_2X4, width)
        graph.add_lumber_piece(rail)
        positions[rail_id] = (x, y, z)
        rotations[rail_id] = (90, 90, 0)

    return graph, positions, rotations


def main():
    """Demonstrate workbench examples."""
    print("Creating workbench examples...")
    print("=" * 60)

    # Example 1: Traditional Heavy-Duty Workbench
    print("\n1. Heavy-Duty Workbench")
    print("-" * 30)
    graph1, positions1, rotations1 = create_workbench(
        length=2000, width=700, height=900, with_shelf=True
    )
    print(f"Created workbench with {graph1.node_count()} pieces")
    print(f"Number of joints: {graph1.edge_count()}")

    # Convert to build123d
    assembly1 = graph_to_assembly(graph1, positions1, rotations1)
    if assembly1:
        print("Successfully converted to build123d assembly")

    # Example 2: Mobile Workbench
    print("\n2. Mobile Workbench")
    print("-" * 30)
    graph2, positions2, rotations2 = create_mobile_workbench(
        length=1200, width=600, height=850
    )
    print(f"Created mobile workbench with {graph2.node_count()} pieces")

    # Convert to build123d
    assembly2 = graph_to_assembly(graph2, positions2, rotations2)
    if assembly2:
        print("Successfully converted to build123d assembly")

    # Print summary
    print("\n" + "=" * 60)
    print("Workbench Features:")
    print("- Heavy-duty construction with doubled legs")
    print("- Multiple work surface boards for strength")
    print("- Optional lower shelf for storage")
    print("- Diagonal braces for stability")
    print("- Mobile version with tool storage")

    print("\nTo visualize these designs:")
    print("  from build123d import show")
    print("  show(assembly1)  # Heavy-duty workbench")
    print("  show(assembly2)  # Mobile workbench")

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
