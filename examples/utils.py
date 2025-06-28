"""Utility functions for working with nichiyou-daiku examples.

This module provides helper functions for common tasks when working with
nichiyou-daiku models, such as visualization helpers and pattern generators.
"""

from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.model import Model, PiecePair
from nichiyou_daiku.core.connection import Connection, BasePosition, Anchor
from nichiyou_daiku.core.geometry import FromMax, FromMin
from nichiyou_daiku.core.geometry import Edge, EdgePoint
from nichiyou_daiku.core.assembly import Assembly


def create_grid_frame(
    rows: int, 
    cols: int, 
    cell_width: float, 
    cell_height: float,
    piece_type: PieceType = PieceType.PT_2x4
) -> Model:
    """Create a grid frame structure.
    
    This helper creates a rectangular grid of connected pieces,
    useful for shelving units, room dividers, or lattice structures.
    
    Args:
        rows: Number of horizontal rows
        cols: Number of vertical columns
        cell_width: Width of each cell in mm
        cell_height: Height of each cell in mm
        piece_type: Type of lumber to use
        
    Returns:
        Model representing the grid frame
        
    Example:
        >>> # Create a 3x3 grid with 200mm cells
        >>> grid = create_grid_frame(3, 3, 200.0, 200.0)
        >>> assembly = Assembly.of(grid)
    """
    pieces = []
    connections = []
    
    # Create horizontal pieces (rows)
    for row in range(rows + 1):
        piece_id = f"horizontal_{row}"
        length = cols * cell_width
        piece = Piece.of(piece_type, length, piece_id)
        pieces.append(piece)
    
    # Create vertical pieces (columns)
    for col in range(cols + 1):
        piece_id = f"vertical_{col}"
        length = rows * cell_height
        piece = Piece.of(piece_type, length, piece_id)
        pieces.append(piece)
    
    # Connect pieces at intersections
    for row in range(rows + 1):
        for col in range(cols + 1):
            horizontal = pieces[row]  # horizontal pieces are first in list
            vertical = pieces[(rows + 1) + col]  # vertical pieces follow
            
            # Connect vertical piece to horizontal piece
            connections.append((
                PiecePair(base=horizontal, target=vertical),
                Connection.of(
                    base=BasePosition(
                        face="front",
                        offset=FromMax(value=col * cell_width)
                    ),
                    target=Anchor(
                        face="bottom",
                        edge_point=EdgePoint(
                            edge=Edge(lhs="bottom", rhs="front"),
                            value=row * cell_height
                        )
                    )
                )
            ))
    
    return Model.of(pieces=pieces, connections=connections)


def create_box_frame(
    width: float,
    depth: float,
    height: float,
    piece_type: PieceType = PieceType.PT_2x4
) -> Model:
    """Create a simple box frame (cube or rectangular prism).
    
    Creates 12 pieces forming the edges of a box, useful as a base
    for many furniture projects.
    
    Args:
        width: Width of the box in mm
        depth: Depth of the box in mm  
        height: Height of the box in mm
        piece_type: Type of lumber to use
        
    Returns:
        Model representing the box frame
    """
    pieces = []
    connections = []
    
    # Create the 12 edge pieces
    # 4 horizontal pieces for top
    top_front = Piece.of(piece_type, width, "top_front")
    top_back = Piece.of(piece_type, width, "top_back")
    top_left = Piece.of(piece_type, depth, "top_left")
    top_right = Piece.of(piece_type, depth, "top_right")
    
    # 4 horizontal pieces for bottom
    bottom_front = Piece.of(piece_type, width, "bottom_front")
    bottom_back = Piece.of(piece_type, width, "bottom_back")
    bottom_left = Piece.of(piece_type, depth, "bottom_left")
    bottom_right = Piece.of(piece_type, depth, "bottom_right")
    
    # 4 vertical pieces
    vert_fl = Piece.of(piece_type, height, "vert_front_left")
    vert_fr = Piece.of(piece_type, height, "vert_front_right")
    vert_bl = Piece.of(piece_type, height, "vert_back_left")
    vert_br = Piece.of(piece_type, height, "vert_back_right")
    
    pieces = [
        top_front, top_back, top_left, top_right,
        bottom_front, bottom_back, bottom_left, bottom_right,
        vert_fl, vert_fr, vert_bl, vert_br
    ]
    
    # Connect vertical pieces to form corners
    # Front left corner
    connections.append((
        PiecePair(base=vert_fl, target=top_front),
        Connection.of(
            base=BasePosition(face="front", offset=FromMax(value=0.0)),
            target=Anchor(
                face="left",
                edge_point=EdgePoint(edge=Edge(lhs="left", rhs="top"), offset=FromMin(value=0.0))
            )
        )
    ))
    
    connections.append((
        PiecePair(base=vert_fl, target=top_left),
        Connection.of(
            base=BasePosition(face="left", offset=FromMax(value=0.0)),
            target=Anchor(
                face="front", 
                edge_point=EdgePoint(edge=Edge(lhs="front", rhs="top"), offset=FromMin(value=0.0))
            )
        )
    ))
    
    # Add more connections as needed...
    # (Full implementation would connect all 12 pieces properly)
    
    return Model.of(pieces=pieces, connections=connections)


def visualize_piece_axes(piece: Piece) -> None:
    """Visualize a single piece with coordinate axes for debugging.
    
    This helper function creates a visual representation of a piece
    with colored axes showing the local coordinate system.
    
    Args:
        piece: The piece to visualize
        
    Note:
        Requires build123d and ocp_vscode to be installed.
    """
    try:
        from build123d import Box, Compound, Color
        from ocp_vscode import show
        
        # Create a simple model with just this piece
        model = Model.of(pieces=[piece], connections=[])
        assembly = Assembly.of(model)
        
        # Get the box for this piece
        box = assembly.boxes[piece.id]
        shape = box.shape
        
        # Create the main box
        main_box = Box(
            length=float(shape.length),
            width=float(shape.width), 
            height=float(shape.height)
        )
        
        # Create axis indicators (small boxes extending from origin)
        x_axis = Box(length=float(shape.length) * 0.3, width=2, height=2)
        x_axis.color = Color("red")
        
        y_axis = Box(length=2, width=float(shape.width) * 0.3, height=2)
        y_axis.color = Color("green")
        
        z_axis = Box(length=2, width=2, height=float(shape.height) * 0.3)
        z_axis.color = Color("blue")
        
        # Show all together
        show(Compound(children=[main_box, x_axis, y_axis, z_axis]), name=f"Piece: {piece.id}")
        
        print(f"Piece '{piece.id}' dimensions:")
        print(f"  Length (X): {shape.length}mm")
        print(f"  Width (Y): {shape.width}mm")  
        print(f"  Height (Z): {shape.height}mm")
        print("Axes: X=Red, Y=Green, Z=Blue")
        
    except ImportError:
        print("Visualization requires build123d and ocp_vscode packages")


def get_connection_summary(model: Model) -> str:
    """Generate a human-readable summary of all connections in a model.
    
    Args:
        model: The model to summarize
        
    Returns:
        String containing connection details
    """
    lines = [f"Model has {len(model.pieces)} pieces and {len(model.connections)} connections:\n"]
    
    for pair, connection in model.connections.items():
        base_pos = connection.joint1.position
        target_pos = connection.joint2.position
        
        lines.append(f"Connection: {pair.target.id} → {pair.base.id}")
        lines.append(f"  Base position: ({base_pos.x:.1f}, {base_pos.y:.1f}, {base_pos.z:.1f})")
        lines.append(f"  Target position: ({target_pos.x:.1f}, {target_pos.y:.1f}, {target_pos.z:.1f})")
        lines.append("")
    
    return "\n".join(lines)


# Example usage
if __name__ == "__main__":
    # Create a simple 2x2 grid
    grid = create_grid_frame(2, 2, 150.0, 150.0)
    print(get_connection_summary(grid))
    
    # Visualize a single piece with axes
    test_piece = Piece.of(PieceType.PT_2x4, 300.0, "test")
    visualize_piece_axes(test_piece)