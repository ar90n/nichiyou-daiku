"""Convert woodworking graph to build123d objects."""

from typing import Optional, Tuple, Dict
import logging

from build123d import Box, Compound, Location, Solid

from nichiyou_daiku.graph.woodworking_graph import WoodworkingGraph
from nichiyou_daiku.core.lumber import LumberPiece

# Type aliases
Position3D = Tuple[float, float, float]
Rotation3D = Tuple[float, float, float]

logger = logging.getLogger(__name__)


def lumber_to_box(
    piece: LumberPiece,
    position: Optional[Position3D] = None,
    rotation: Optional[Rotation3D] = None,
) -> Solid:
    """Convert a lumber piece to a build123d Box.

    This is a standalone function for Task 4.2.

    Args:
        piece: The lumber piece to convert
        position: Optional position (x, y, z) in millimeters
        rotation: Optional rotation (rx, ry, rz) in degrees

    Returns:
        A build123d Box solid with correct dimensions and position
    """
    # Get dimensions from lumber type
    dimensions = piece.get_dimensions()
    width, height, length = dimensions

    # Create box at origin (note: build123d expects length, width, height order)
    box = Box(length, width, height)

    # Apply position and rotation if specified
    if position is None:
        position = (0, 0, 0)
    if rotation is None:
        rotation = (0, 0, 0)

    if position != (0, 0, 0) or rotation != (0, 0, 0):
        location = Location(position)
        if rotation != (0, 0, 0):
            # Apply rotations in order: X, Y, Z
            rx, ry, rz = rotation
            if rx != 0:
                location = location * Location((0, 0, 0), (1, 0, 0), rx)
            if ry != 0:
                location = location * Location((0, 0, 0), (0, 1, 0), ry)
            if rz != 0:
                location = location * Location((0, 0, 0), (0, 0, 1), rz)
        box = box.located(location)

    return box


def graph_to_assembly(
    graph: WoodworkingGraph,
    positions: Optional[Dict[str, Position3D]] = None,
    rotations: Optional[Dict[str, Rotation3D]] = None,
) -> Optional[Compound]:
    """Convert a woodworking graph to a build123d assembly.

    This is a standalone function for Task 4.3.

    Args:
        graph: The woodworking graph to convert
        positions: Optional mapping of node_id to position (x, y, z)
        rotations: Optional mapping of node_id to rotation (rx, ry, rz)

    Returns:
        A build123d Compound containing all pieces,
        or None if graph is empty
    """
    # Default empty dicts if not provided
    if positions is None:
        positions = {}
    if rotations is None:
        rotations = {}

    # Collect all boxes
    boxes = []
    for node_id in graph._graph.nodes():
        node_data = graph.get_lumber_data(node_id)
        piece = node_data.lumber_piece

        # Get position and rotation for this piece
        position = positions.get(node_id)
        rotation = rotations.get(node_id)

        box = lumber_to_box(piece, position, rotation)
        boxes.append(box)

    # Return compound or None if no pieces
    if not boxes:
        logger.warning("No pieces in graph to convert")
        return None

    return Compound(children=boxes)


class GraphToBuild123D:
    """Convert woodworking graph to build123d objects.

    This is a simple converter that creates build123d Box objects from lumber pieces
    and combines them into a Compound. Visualization is handled by build123d's
    built-in show() method.
    """

    def __init__(self):
        """Initialize the converter."""
        pass

    def lumber_to_box(
        self,
        piece: LumberPiece,
        position: Optional[Position3D] = None,
        rotation: Optional[Rotation3D] = None,
    ) -> Solid:
        """Convert a lumber piece to a build123d Box.

        This method delegates to the standalone lumber_to_box function.

        Args:
            piece: The lumber piece to convert
            position: Optional position (x, y, z) in millimeters
            rotation: Optional rotation (rx, ry, rz) in degrees

        Returns:
            A build123d Box solid with correct dimensions and position
        """
        return lumber_to_box(piece, position, rotation)

    def graph_to_compound(
        self,
        graph: WoodworkingGraph,
        positions: Optional[Dict[str, Position3D]] = None,
        rotations: Optional[Dict[str, Rotation3D]] = None,
    ) -> Optional[Compound]:
        """Convert a woodworking graph to a build123d Compound.

        This method delegates to the standalone graph_to_assembly function.

        Args:
            graph: The woodworking graph to convert
            positions: Optional mapping of node_id to position (x, y, z)
            rotations: Optional mapping of node_id to rotation (rx, ry, rz)

        Returns:
            A build123d Compound containing all pieces,
            or None if graph is empty
        """
        return graph_to_assembly(graph, positions, rotations)

    def convert(self, graph: WoodworkingGraph) -> Optional[Compound]:
        """Main conversion method.

        This is an alias for graph_to_compound for backwards compatibility.

        Args:
            graph: The woodworking graph to convert

        Returns:
            A build123d Compound containing all pieces
        """
        return self.graph_to_compound(graph)
