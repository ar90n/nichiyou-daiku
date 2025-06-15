"""Graph-based representation of woodworking assemblies.

This module provides a graph structure for managing lumber pieces and their
connections, enabling complex assembly modeling and analysis.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import networkx as nx

from nichiyou_daiku.core.lumber import LumberPiece, Face, LumberType
from nichiyou_daiku.connectors.general import GeneralJoint


# Type aliases
Position3D = Tuple[float, float, float]
Rotation3D = Tuple[float, float, float]


@dataclass(frozen=True)
class NodeData:
    """Data stored in graph nodes representing lumber pieces.

    Attributes:
        lumber_piece: The lumber piece this node represents
    """

    lumber_piece: LumberPiece


@dataclass(frozen=True)
class EdgeData:
    """Data stored in graph edges representing connections.

    Attributes:
        joint: The joint connecting two lumber pieces
        assembly_order: Optional order for assembly sequence
    """

    joint: GeneralJoint
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

    def add_lumber_piece(self, lumber: LumberPiece) -> None:
        """Add a lumber piece as a node in the graph.

        Args:
            lumber: The lumber piece to add

        Raises:
            ValueError: If lumber ID already exists in graph
        """
        if lumber.id in self._graph:
            raise ValueError(f"Lumber piece '{lumber.id}' already exists in graph")

        node_data = NodeData(lumber_piece=lumber)
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
        joint: GeneralJoint,
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

    # Subgraph operations

    def extract_subgraph(self, lumber_ids: List[str]) -> "WoodworkingGraph":
        """Extract a subgraph containing only specified lumber pieces.

        Args:
            lumber_ids: List of lumber IDs to include

        Returns:
            New WoodworkingGraph with only specified pieces and their joints
        """
        # Create subgraph with NetworkX
        subgraph_nx = self._graph.subgraph(lumber_ids).copy()

        # Create new WoodworkingGraph
        subgraph = WoodworkingGraph()
        subgraph._graph = subgraph_nx

        return subgraph

    def merge_graph(self, other: "WoodworkingGraph") -> None:
        """Merge another graph into this one.

        Args:
            other: Graph to merge in

        Raises:
            ValueError: If there are conflicting lumber IDs
        """
        # Check for conflicts
        common_nodes = set(self._graph.nodes()) & set(other._graph.nodes())
        if common_nodes:
            raise ValueError(f"Conflicting lumber IDs: {common_nodes}")

        # Merge the graphs
        self._graph = nx.compose(self._graph, other._graph)

    def get_connected_components(self) -> List[List[str]]:
        """Get all connected components in the graph.

        Returns:
            List of components, each component is a list of lumber IDs
        """
        # Convert to undirected for component analysis
        undirected = self._graph.to_undirected()
        components = list(nx.connected_components(undirected))
        # Sort each component for deterministic ordering
        return [sorted(list(component)) for component in components]

    # Path finding and cycle detection

    def find_path(self, start_id: str, end_id: str) -> Optional[List[str]]:
        """Find a path between two lumber pieces.

        Args:
            start_id: Starting lumber ID
            end_id: Ending lumber ID

        Returns:
            List of lumber IDs forming a path, or None if no path exists
        """
        try:
            return nx.shortest_path(self._graph, start_id, end_id)
        except nx.NetworkXNoPath:
            return None

    def has_cycles(self) -> bool:
        """Check if the graph contains any cycles.

        Returns:
            True if cycles exist, False otherwise
        """
        return not nx.is_directed_acyclic_graph(self._graph)

    def find_cycles(self) -> List[List[str]]:
        """Find all simple cycles in the graph.

        Returns:
            List of cycles, each cycle is a list of lumber IDs
        """
        return list(nx.simple_cycles(self._graph))

    # Query operations

    def find_pieces_by_type(self, lumber_type: LumberType) -> List[str]:
        """Find all lumber pieces of a specific type.

        Args:
            lumber_type: Type of lumber to search for

        Returns:
            List of lumber IDs matching the type
        """
        matching_ids = []
        for node_id, data in self._graph.nodes(data=True):
            node_data = data.get("data")
            if node_data and node_data.lumber_piece.lumber_type == lumber_type:
                matching_ids.append(node_id)
        return matching_ids

    def get_assembly_bounds(self) -> Tuple[Position3D, Position3D]:
        """Calculate the bounding box of the entire assembly.

        Returns:
            Tuple of (min_corner, max_corner) positions
        """
        if self.node_count() == 0:
            return ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))

        min_x = min_y = min_z = float("inf")
        max_x = max_y = max_z = float("-inf")

        # Check all lumber pieces with consistent origin per component
        components = self.get_connected_components()

        for component in components:
            # Use first node as origin for this component
            component_origin = component[0]

            for node_id in component:
                lumber = self.get_lumber_data(node_id).lumber_piece
                dims = lumber.get_dimensions()
                width, height, length = dims

                # Get piece origin relative to component origin
                origin = calculate_piece_origin_position(
                    self, node_id, origin_id=component_origin
                )

                # Update bounds
                min_x = min(min_x, origin[0])
                min_y = min(min_y, origin[1])
                min_z = min(min_z, origin[2])

                max_x = max(max_x, origin[0] + length)
                max_y = max(max_y, origin[1] + width)
                max_z = max(max_z, origin[2] + height)

        return ((min_x, min_y, min_z), (max_x, max_y, max_z))

    def count_joints_by_face(self, face: Face) -> int:
        """Count how many joints connect to a specific face type.

        Args:
            face: Face type to count

        Returns:
            Number of joints using this face
        """
        count = 0
        for _, _, data in self._graph.edges(data=True):
            edge_data = data.get("data")
            if edge_data:
                joint = edge_data.joint
                if joint.base_loc.face == face or joint.target_loc.face == face:
                    count += 1
        return count


# Functional helpers for graph operations


def create_lumber_node(lumber: LumberPiece) -> NodeData:
    """Create a node data instance for a lumber piece.

    Args:
        lumber: The lumber piece

    Returns:
        NodeData instance
    """
    return NodeData(lumber_piece=lumber)


def create_joint_edge(
    joint: GeneralJoint, assembly_order: Optional[int] = None
) -> EdgeData:
    """Create an edge data instance for a joint.

    Args:
        joint: The joint
        assembly_order: Optional assembly sequence

    Returns:
        EdgeData instance
    """
    return EdgeData(joint=joint, assembly_order=assembly_order)


# OBSOLETE: Position calculation functions below are deprecated with the new joint system
# They are kept temporarily for backward compatibility with tests

def calculate_piece_origin_position(
    graph: WoodworkingGraph, lumber_id: str, origin_id: Optional[str] = None
) -> Position3D:
    """Calculate the origin position of a lumber piece.

    The origin is at the left-top corner of the bottom face.

    Args:
        graph: The woodworking graph
        lumber_id: ID of lumber to calculate position for
        origin_id: ID of origin piece (defaults to lumber_id itself)

    Returns:
        World position of the lumber piece origin
    """
    if origin_id is None or lumber_id == origin_id:
        # This is the origin piece - its origin is at world origin
        return (0.0, 0.0, 0.0)

    # Get the center position for connected pieces
    center_pos = _calculate_piece_center_position_connected(graph, lumber_id, origin_id)

    # Get lumber dimensions to calculate offset from center to origin
    lumber = graph.get_lumber_data(lumber_id).lumber_piece
    dims = lumber.get_dimensions()
    width, height, length = dims

    # Origin is at left-top of bottom face
    # Center to origin offset: (-length/2, -width/2, -height/2)
    origin_pos = (
        center_pos[0] - length / 2,
        center_pos[1] - width / 2,
        center_pos[2] - height / 2,
    )

    return origin_pos


def calculate_world_position(
    graph: WoodworkingGraph, lumber_id: str, face: Face, origin_id: Optional[str] = None
) -> Position3D:
    """Calculate world position of a face center on a lumber piece.

    Args:
        graph: The woodworking graph
        lumber_id: ID of lumber piece
        face: Which face to get the center of
        origin_id: ID of origin piece (defaults to lumber_id itself)

    Returns:
        World position of the face center
    """
    # Get the lumber piece
    lumber = graph.get_lumber_data(lumber_id).lumber_piece

    # For single pieces, their center is at world origin
    # For connected pieces, we calculate based on graph traversal
    if origin_id is None or lumber_id == origin_id:
        # Single piece - center at origin
        local_face_center = lumber.get_face_center_local(face)
        return local_face_center

    # Get piece center position through graph traversal
    piece_center = _calculate_piece_center_position_connected(
        graph, lumber_id, origin_id
    )

    # Get face center in local coordinates (relative to piece center)
    local_face_center = lumber.get_face_center_local(face)

    # Add to world center position
    world_pos = (
        piece_center[0] + local_face_center[0],
        piece_center[1] + local_face_center[1],
        piece_center[2] + local_face_center[2],
    )

    return world_pos


# Helper functions for position calculations


def _calculate_piece_center_position_connected(
    graph: WoodworkingGraph, lumber_id: str, origin_id: str
) -> Position3D:
    """Calculate center position for connected pieces.

    For connected pieces, the origin piece has its origin (not center) at (0,0,0).
    """
    # Get origin piece to find its center offset
    origin_lumber = graph.get_lumber_data(origin_id).lumber_piece
    origin_dims = origin_lumber.get_dimensions()
    origin_width, origin_height, origin_length = origin_dims

    # Origin piece center is offset from its origin
    origin_center = (origin_length / 2, origin_width / 2, origin_height / 2)

    # If this is the origin piece, return its center
    if lumber_id == origin_id:
        return origin_center

    # Find path from origin to target (use undirected for connectivity)
    try:
        undirected = graph._graph.to_undirected()
        path = nx.shortest_path(undirected, origin_id, lumber_id)
    except nx.NetworkXNoPath:
        raise ValueError(f"No path from '{origin_id}' to '{lumber_id}'")

    # Start at origin piece center
    current_pos = origin_center
    current_rot = (0.0, 0.0, 0.0)

    # Traverse path and accumulate transformations
    for i in range(len(path) - 1):
        src_id = path[i]
        dst_id = path[i + 1]

        # Get the joint connecting these pieces (check both directions)
        try:
            edge_data = graph.get_joint_data(src_id, dst_id)
            joint = edge_data.joint
            forward = True
        except KeyError:
            # Try reverse direction
            edge_data = graph.get_joint_data(dst_id, src_id)
            joint = edge_data.joint
            forward = False

        # Get lumber pieces
        if forward:
            src_lumber = graph.get_lumber_data(src_id).lumber_piece
            dst_lumber = graph.get_lumber_data(dst_id).lumber_piece
            # Calculate position offset based on joint connection
            dst_offset = _calculate_joint_offset(
                src_lumber, dst_lumber, joint, current_rot
            )
        else:
            # Reverse direction - need to invert the offset calculation
            src_lumber = graph.get_lumber_data(dst_id).lumber_piece
            dst_lumber = graph.get_lumber_data(src_id).lumber_piece
            # Calculate reverse offset
            forward_offset = _calculate_joint_offset(
                src_lumber, dst_lumber, joint, current_rot
            )
            # Invert the offset
            dst_offset = (-forward_offset[0], -forward_offset[1], -forward_offset[2])

        # Update position
        current_pos = (
            current_pos[0] + dst_offset[0],
            current_pos[1] + dst_offset[1],
            current_pos[2] + dst_offset[2],
        )

    return current_pos


# OBSOLETE: EdgePoint-based function - commented out
# def _calculate_edge_point_world(
#     lumber: LumberPiece,
#     edge_point: EdgePoint,
#     origin_pos: Position3D,
#     rotation: Rotation3D,
# ) -> Position3D:
#     """Calculate world position of an edge point on a lumber piece.
# 
#     Args:
#         lumber: The lumber piece
#         edge_point: The edge point to calculate
#         origin_pos: World position of lumber origin
#         rotation: World rotation of lumber
# 
#     Returns:
#         World position of the edge point
#     """
#     # This is a simplified implementation
#     # Full implementation would calculate exact edge position
#     # based on face intersection and parametric position
#     return origin_pos


def _calculate_joint_offset(
    src_lumber: LumberPiece,
    dst_lumber: LumberPiece,
    joint: GeneralJoint,
    current_rotation: Rotation3D,
) -> Position3D:
    """Calculate offset for destination piece center based on joint alignment.

    Args:
        src_lumber: Source lumber piece
        dst_lumber: Destination lumber piece
        joint: The joint connecting them
        current_rotation: Current world rotation

    Returns:
        Offset to apply for destination piece center
    """
    # Get dimensions
    src_dims = src_lumber.get_dimensions()
    dst_dims = dst_lumber.get_dimensions()
    src_width, src_height, src_length = src_dims
    dst_width, dst_height, dst_length = dst_dims

    # This function is obsolete with the new joint system
    # The new system uses build123d's RigidJoint for automatic positioning
    # Return zero offset as a placeholder until this function is removed
    return (0.0, 0.0, 0.0)
