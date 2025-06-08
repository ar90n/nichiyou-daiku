"""Example: Parametric furniture design with nichiyou-daiku.

This example demonstrates:
1. Parametric design patterns
2. Creating furniture that adapts to space constraints
3. Modular and scalable designs
"""

from typing import List, Tuple
from nichiyou_daiku.core.lumber import LumberPiece, LumberType
from nichiyou_daiku.graph.woodworking_graph import WoodworkingGraph
from nichiyou_daiku.rendering.build123d_converter import graph_to_assembly


def create_parametric_storage_unit(
    total_width: float,
    total_height: float,
    total_depth: float,
    compartment_sizes: List[Tuple[float, float]],
) -> tuple[WoodworkingGraph, dict, dict]:
    """Create a storage unit with custom compartment sizes.

    This creates a storage unit where compartments can have different
    widths and heights, optimized for specific storage needs.

    Args:
        total_width: Total unit width in mm
        total_height: Total unit height in mm
        total_depth: Total unit depth in mm
        compartment_sizes: List of (width_ratio, height_ratio) for each compartment

    Returns:
        Tuple of (graph, positions, rotations)
    """
    graph = WoodworkingGraph()
    positions = {}
    rotations = {}

    thickness = 38  # 2x lumber

    # Create outer frame
    # Sides
    left_side = LumberPiece("left_side", LumberType.LUMBER_2X16, total_height)
    right_side = LumberPiece("right_side", LumberType.LUMBER_2X16, total_height)
    graph.add_lumber_piece(left_side)
    graph.add_lumber_piece(right_side)

    positions["left_side"] = (0, 0, 0)
    positions["right_side"] = (total_width - thickness, 0, 0)

    # Top and bottom
    top = LumberPiece("top", LumberType.LUMBER_2X16, total_width)
    bottom = LumberPiece("bottom", LumberType.LUMBER_2X16, total_width)
    graph.add_lumber_piece(top)
    graph.add_lumber_piece(bottom)

    positions["top"] = (0, 0, total_height - thickness)
    rotations["top"] = (0, 90, 0)
    positions["bottom"] = (0, 0, 0)
    rotations["bottom"] = (0, 90, 0)

    # Create compartments based on specifications
    current_x = thickness
    compartment_id = 0

    for width_ratio, height_ratio in compartment_sizes:
        compartment_width = total_width * width_ratio
        compartment_height = total_height * height_ratio

        # Add vertical divider (if not at the end)
        if current_x + compartment_width < total_width - thickness:
            divider_id = f"v_divider_{compartment_id}"
            divider = LumberPiece(divider_id, LumberType.LUMBER_2X8, total_height)
            graph.add_lumber_piece(divider)
            positions[divider_id] = (current_x + compartment_width, 0, 0)

        # Add horizontal shelf for this compartment
        if compartment_height < total_height - thickness:
            shelf_id = f"shelf_{compartment_id}"
            shelf = LumberPiece(shelf_id, LumberType.LUMBER_2X8, compartment_width)
            graph.add_lumber_piece(shelf)
            positions[shelf_id] = (current_x, 0, compartment_height)
            rotations[shelf_id] = (0, 90, 0)

        current_x += compartment_width
        compartment_id += 1

    # Add back panel
    back = LumberPiece("back_panel", LumberType.LUMBER_1X16, total_width)
    graph.add_lumber_piece(back)
    positions["back_panel"] = (0, total_depth - 19, 0)
    rotations["back_panel"] = (90, 0, 0)

    return graph, positions, rotations


def create_adjustable_desk(
    width: float = 1200,
    depth: float = 600,
    min_height: float = 700,
    max_height: float = 1100,
    shelf_positions: List[float] = [0.3, 0.7],
) -> tuple[WoodworkingGraph, dict, dict]:
    """Create a desk with adjustable height and shelving.

    Args:
        width: Desk width in mm
        depth: Desk depth in mm
        min_height: Minimum desk height in mm
        max_height: Maximum desk height in mm
        shelf_positions: Relative positions for shelves (0-1)

    Returns:
        Tuple of (graph, positions, rotations) for mid-height configuration
    """
    graph = WoodworkingGraph()
    positions = {}
    rotations = {}

    # Use mid-height for default configuration
    height = (min_height + max_height) / 2
    thickness = 38

    # Create telescoping legs (simplified - using fixed height)
    # In reality, would have inner and outer leg pieces
    for i in range(4):
        leg_id = f"leg_{i}"
        leg = LumberPiece(leg_id, LumberType.LUMBER_2X4, height)
        graph.add_lumber_piece(leg)

        # Position legs at corners
        x = (i % 2) * (width - thickness)
        y = (i // 2) * (depth - thickness)
        positions[leg_id] = (x, y, 0)

    # Desktop (multiple boards for strength)
    desktop_boards = 3
    board_width = depth / desktop_boards

    for i in range(desktop_boards):
        desktop_id = f"desktop_{i}"
        desktop = LumberPiece(desktop_id, LumberType.LUMBER_2X8, width)
        graph.add_lumber_piece(desktop)

        y_pos = i * board_width
        positions[desktop_id] = (0, y_pos, height)
        rotations[desktop_id] = (0, 0, 0)

    # Add cable management tray
    cable_tray = LumberPiece("cable_tray", LumberType.LUMBER_1X4, width - 200)
    graph.add_lumber_piece(cable_tray)
    positions["cable_tray"] = (100, depth - 100, height - 100)
    rotations["cable_tray"] = (0, 90, 0)

    # Add adjustable shelves
    for idx, shelf_pos in enumerate(shelf_positions):
        shelf_height = min_height + (max_height - min_height) * shelf_pos
        shelf_id = f"adj_shelf_{idx}"
        shelf = LumberPiece(shelf_id, LumberType.LUMBER_1X8, width - 100)
        graph.add_lumber_piece(shelf)

        positions[shelf_id] = (50, depth / 2, shelf_height)
        rotations[shelf_id] = (0, 90, 0)

    # Add monitor stand/riser
    riser_height = 150
    riser_width = 500

    # Riser legs
    for i in range(2):
        riser_leg_id = f"riser_leg_{i}"
        riser_leg = LumberPiece(riser_leg_id, LumberType.LUMBER_2X4, riser_height)
        graph.add_lumber_piece(riser_leg)

        x_pos = (width - riser_width) / 2 + i * (riser_width - thickness)
        positions[riser_leg_id] = (x_pos, depth / 4, height)

    # Riser top
    riser_top = LumberPiece("riser_top", LumberType.LUMBER_1X8, riser_width)
    graph.add_lumber_piece(riser_top)
    positions["riser_top"] = (
        (width - riser_width) / 2,
        depth / 4,
        height + riser_height,
    )
    rotations["riser_top"] = (0, 0, 0)

    return graph, positions, rotations


def create_modular_room_divider(
    num_columns: int = 4,
    num_rows: int = 5,
    cell_size: float = 300,
    pattern: List[List[bool]] = None,
) -> tuple[WoodworkingGraph, dict, dict]:
    """Create a modular room divider with customizable open/closed cells.

    Args:
        num_columns: Number of columns
        num_rows: Number of rows
        cell_size: Size of each cell in mm
        pattern: 2D boolean array for open (True) or shelf (False) cells

    Returns:
        Tuple of (graph, positions, rotations)
    """
    graph = WoodworkingGraph()
    positions = {}
    rotations = {}

    thickness = 38

    # Default pattern - checkerboard
    if pattern is None:
        pattern = [
            [(i + j) % 2 == 0 for j in range(num_columns)] for i in range(num_rows)
        ]

    # Create vertical members
    for i in range(num_columns + 1):
        vert_id = f"vertical_{i}"
        vert = LumberPiece(vert_id, LumberType.LUMBER_2X8, num_rows * cell_size)
        graph.add_lumber_piece(vert)
        positions[vert_id] = (i * cell_size, 0, 0)

    # Create horizontal members
    for j in range(num_rows + 1):
        horiz_id = f"horizontal_{j}"
        horiz = LumberPiece(
            horiz_id, LumberType.LUMBER_2X8, num_columns * cell_size + thickness
        )
        graph.add_lumber_piece(horiz)
        positions[horiz_id] = (0, 0, j * cell_size)
        rotations[horiz_id] = (0, 90, 0)

    # Add backs or shelves based on pattern
    for i in range(num_rows):
        for j in range(num_columns):
            if not pattern[i][j]:  # Add shelf/back
                cell_id = f"cell_{i}_{j}"
                cell_piece = LumberPiece(
                    cell_id, LumberType.LUMBER_1X8, cell_size - thickness
                )
                graph.add_lumber_piece(cell_piece)

                x_pos = j * cell_size + thickness / 2
                z_pos = i * cell_size + thickness / 2
                positions[cell_id] = (x_pos, thickness, z_pos)
                rotations[cell_id] = (0, 0, 0)

    return graph, positions, rotations


def main():
    """Demonstrate parametric furniture examples."""
    print("Creating parametric furniture examples...")
    print("=" * 60)

    # Example 1: Custom Storage Unit
    print("\n1. Parametric Storage Unit")
    print("-" * 30)

    # Define custom compartments (width_ratio, height_ratio)
    compartments = [
        (0.3, 0.5),  # Small compartment
        (0.3, 0.7),  # Medium compartment
        (0.4, 1.0),  # Tall compartment
    ]

    graph1, positions1, rotations1 = create_parametric_storage_unit(
        total_width=1200,
        total_height=1800,
        total_depth=400,
        compartment_sizes=compartments,
    )
    print(f"Created storage unit with {graph1.node_count()} pieces")

    # Example 2: Adjustable Desk
    print("\n2. Adjustable Height Desk")
    print("-" * 30)

    graph2, positions2, rotations2 = create_adjustable_desk(
        width=1400,
        depth=700,
        min_height=650,
        max_height=1150,
        shelf_positions=[0.25, 0.6, 0.85],
    )
    print(f"Created adjustable desk with {graph2.node_count()} pieces")

    # Example 3: Room Divider
    print("\n3. Modular Room Divider")
    print("-" * 30)

    # Create custom pattern
    custom_pattern = [
        [True, False, True, False, True],
        [False, True, True, True, False],
        [True, True, False, True, True],
        [False, True, True, True, False],
        [True, False, True, False, True],
    ]

    graph3, positions3, rotations3 = create_modular_room_divider(
        num_columns=5, num_rows=5, cell_size=350, pattern=custom_pattern
    )
    print(f"Created room divider with {graph3.node_count()} pieces")

    # Convert all to build123d
    assemblies = []
    for graph, positions, rotations in [
        (graph1, positions1, rotations1),
        (graph2, positions2, rotations2),
        (graph3, positions3, rotations3),
    ]:
        assembly = graph_to_assembly(graph, positions, rotations)
        if assembly:
            assemblies.append(assembly)

    print("\n" + "=" * 60)
    print("Parametric Design Benefits:")
    print("- Easily adjust dimensions to fit specific spaces")
    print("- Create variations from the same base design")
    print("- Optimize material usage for custom needs")
    print("- Generate cut lists automatically")

    print("\nTo visualize:")
    print("  from build123d import show")
    print("  show(assemblies[0])  # Storage unit")
    print("  show(assemblies[1])  # Adjustable desk")
    print("  show(assemblies[2])  # Room divider")

    return assemblies


if __name__ == "__main__":
    try:
        assemblies = main()
    except ImportError as e:
        print(f"\nNote: {e}")
        print("build123d requires proper graphical environment for visualization.")
