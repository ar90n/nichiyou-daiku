"""Graph-based representation of woodworking assemblies.

This module provides a graph structure for managing lumber pieces and their
connections, enabling complex assembly modeling and analysis.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import networkx as nx

from nichiyou_daiku.core.lumber import LumberPiece
from nichiyou_daiku.connectors.aligned_screw import AlignedScrewJoint


# Type aliases
Position3D = Tuple[float, float, float]
Rotation3D = Tuple[float, float, float]


@dataclass(frozen=True)
class NodeData:
    """Data stored in graph nodes representing lumber pieces.

    Attributes:
        lumber_piece: The lumber piece this node represents
        local_position: Position relative to parent (or world if root)
        local_rotation: Rotation relative to parent (or world if root)
    """

    lumber_piece: LumberPiece
    local_position: Position3D = (0.0, 0.0, 0.0)
    local_rotation: Rotation3D = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class EdgeData:
    """Data stored in graph edges representing connections.

    Attributes:
        joint: The joint connecting two lumber pieces
        assembly_order: Optional order for assembly sequence
    """

    joint: AlignedScrewJoint
    assembly_order: Optional[int] = None


class WoodworkingGraph:
    """Graph representation of a woodworking assembly.

    This class wraps a NetworkX MultiDiGraph to represent furniture
    assemblies. Nodes represent lumber pieces and edges represent
    joints between them.
    """

    def __init__(self):
        """Initialize an empty woodworking graph."""
        self._graph = nx.MultiDiGraph()

    # Node operations

    def add_lumber_piece(
        self,
        lumber: LumberPiece,
        position: Position3D = (0.0, 0.0, 0.0),
        rotation: Rotation3D = (0.0, 0.0, 0.0),
    ) -> None:
        """Add a lumber piece as a node in the graph.

        Args:
            lumber: The lumber piece to add
            position: Local position relative to parent
            rotation: Local rotation relative to parent

        Raises:
            ValueError: If lumber ID already exists in graph
        """
        if lumber.id in self._graph:
            raise ValueError(f"Lumber piece '{lumber.id}' already exists in graph")

        node_data = NodeData(
            lumber_piece=lumber, local_position=position, local_rotation=rotation
        )
        self._graph.add_node(lumber.id, data=node_data)

    def has_lumber(self, lumber_id: str) -> bool:
        """Check if a lumber piece exists in the graph."""
        return lumber_id in self._graph

    def get_lumber_data(self, lumber_id: str) -> NodeData:
        """Get the node data for a lumber piece.

        Args:
            lumber_id: ID of the lumber piece

        Returns:
            NodeData for the lumber piece

        Raises:
            KeyError: If lumber ID not found
        """
        if not self.has_lumber(lumber_id):
            raise KeyError(f"Lumber piece '{lumber_id}' not found in graph")
        return self._graph.nodes[lumber_id]["data"]

    def node_count(self) -> int:
        """Get the number of lumber pieces in the graph."""
        return self._graph.number_of_nodes()

    # Edge operations

    def add_joint(
        self,
        src_id: str,
        dst_id: str,
        joint: AlignedScrewJoint,
        assembly_order: Optional[int] = None,
    ) -> None:
        """Add a joint as an edge in the graph.

        Args:
            src_id: ID of source lumber piece
            dst_id: ID of destination lumber piece
            joint: The joint connecting the pieces
            assembly_order: Optional assembly sequence number

        Raises:
            ValueError: If either lumber piece not found
        """
        if not self.has_lumber(src_id):
            raise ValueError(f"Source lumber '{src_id}' not found in graph")
        if not self.has_lumber(dst_id):
            raise ValueError(f"Destination lumber '{dst_id}' not found in graph")

        edge_data = EdgeData(joint=joint, assembly_order=assembly_order)
        self._graph.add_edge(src_id, dst_id, data=edge_data)

    def has_joint(self, src_id: str, dst_id: str) -> bool:
        """Check if a joint exists between two lumber pieces."""
        return self._graph.has_edge(src_id, dst_id)

    def get_joint_data(self, src_id: str, dst_id: str) -> EdgeData:
        """Get the edge data for a joint.

        Args:
            src_id: ID of source lumber piece
            dst_id: ID of destination lumber piece

        Returns:
            EdgeData for the joint

        Raises:
            KeyError: If joint not found
        """
        if not self.has_joint(src_id, dst_id):
            raise KeyError(f"No joint found between '{src_id}' and '{dst_id}'")

        # Get first edge (for single joint case)
        edge_attrs = self._graph.get_edge_data(src_id, dst_id)
        return edge_attrs[0]["data"]

    def get_all_joints(self, src_id: str, dst_id: str) -> List[EdgeData]:
        """Get all joints between two lumber pieces.

        Useful when multiple joints connect the same two pieces.

        Args:
            src_id: ID of source lumber piece
            dst_id: ID of destination lumber piece

        Returns:
            List of EdgeData for all joints
        """
        if not self.has_joint(src_id, dst_id):
            return []

        edge_attrs = self._graph.get_edge_data(src_id, dst_id)
        return [attrs["data"] for attrs in edge_attrs.values()]

    def edge_count(self) -> int:
        """Get the number of joints in the graph."""
        return self._graph.number_of_edges()

    # Graph traversal

    def get_neighbors(self, lumber_id: str) -> List[str]:
        """Get IDs of all lumber pieces connected to the given piece.

        Args:
            lumber_id: ID of lumber piece

        Returns:
            List of connected lumber IDs
        """
        if not self.has_lumber(lumber_id):
            return []

        # Get both predecessors and successors for undirected connectivity
        predecessors = set(self._graph.predecessors(lumber_id))
        successors = set(self._graph.successors(lumber_id))
        return list(predecessors | successors)


# Functional helpers for graph operations


def create_lumber_node(
    lumber: LumberPiece,
    position: Position3D = (0.0, 0.0, 0.0),
    rotation: Rotation3D = (0.0, 0.0, 0.0),
) -> NodeData:
    """Create a node data instance for a lumber piece.

    Args:
        lumber: The lumber piece
        position: Local position
        rotation: Local rotation

    Returns:
        NodeData instance
    """
    return NodeData(
        lumber_piece=lumber, local_position=position, local_rotation=rotation
    )


def create_joint_edge(
    joint: AlignedScrewJoint, assembly_order: Optional[int] = None
) -> EdgeData:
    """Create an edge data instance for a joint.

    Args:
        joint: The joint
        assembly_order: Optional assembly sequence

    Returns:
        EdgeData instance
    """
    return EdgeData(joint=joint, assembly_order=assembly_order)


def calculate_world_position(
    graph: WoodworkingGraph, lumber_id: str, origin_id: Optional[str] = None
) -> Position3D:
    """Calculate world position of a lumber piece by traversing the graph.

    Args:
        graph: The woodworking graph
        lumber_id: ID of lumber to calculate position for
        origin_id: ID of origin piece (defaults to lumber_id itself)

    Returns:
        World position coordinates

    Note:
        This is a simplified implementation. Full implementation would
        traverse the graph from origin to target, accumulating transforms.
    """
    if origin_id is None or lumber_id == origin_id:
        # Return local position as world position
        node_data = graph.get_lumber_data(lumber_id)
        return node_data.local_position

    # For connected pieces, accumulate positions
    # This is a simplified version - real implementation would use
    # graph traversal and proper 3D transformations
    try:
        path = nx.shortest_path(graph._graph, origin_id, lumber_id)
        total_x, total_y, total_z = 0.0, 0.0, 0.0

        for node_id in path:
            node_data = graph.get_lumber_data(node_id)
            pos = node_data.local_position
            total_x += pos[0]
            total_y += pos[1]
            total_z += pos[2]

        return (total_x, total_y, total_z)
    except nx.NetworkXNoPath:
        # No path found, return local position
        node_data = graph.get_lumber_data(lumber_id)
        return node_data.local_position


def calculate_world_rotation(
    graph: WoodworkingGraph, lumber_id: str, origin_id: Optional[str] = None
) -> Rotation3D:
    """Calculate world rotation of a lumber piece by traversing the graph.

    Args:
        graph: The woodworking graph
        lumber_id: ID of lumber to calculate rotation for
        origin_id: ID of origin piece (defaults to lumber_id itself)

    Returns:
        World rotation angles (rx, ry, rz) in degrees

    Note:
        This is a simplified implementation. Full implementation would
        traverse the graph and properly compose rotations.
    """
    node_data = graph.get_lumber_data(lumber_id)

    if origin_id is None or lumber_id == origin_id:
        return node_data.local_rotation

    # Simplified - just return local rotation
    # Real implementation would compose rotations along path
    return node_data.local_rotation
