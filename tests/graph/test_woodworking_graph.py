"""Tests for WoodworkingGraph class."""

import pytest
import networkx as nx

from nichiyou_daiku.graph.woodworking_graph import (
    WoodworkingGraph,
    NodeData,
    EdgeData,
    create_lumber_node,
    create_joint_edge,
    calculate_world_position,
    calculate_world_rotation,
)
from nichiyou_daiku.core.lumber import LumberPiece, LumberType, Face
from nichiyou_daiku.core.geometry import EdgePoint
from nichiyou_daiku.connectors.aligned_screw import AlignedScrewJoint


class TestNodeData:
    """Test NodeData dataclass."""

    def test_node_data_creation(self):
        """Test creating node data."""
        lumber = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        node = NodeData(lumber_piece=lumber)

        assert node.lumber_piece == lumber
        assert node.local_position == (0.0, 0.0, 0.0)
        assert node.local_rotation == (0.0, 0.0, 0.0)

    def test_node_data_with_transform(self):
        """Test node data with position and rotation."""
        lumber = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        node = NodeData(
            lumber_piece=lumber,
            local_position=(100.0, 50.0, 0.0),
            local_rotation=(0.0, 0.0, 90.0),
        )

        assert node.local_position == (100.0, 50.0, 0.0)
        assert node.local_rotation == (0.0, 0.0, 90.0)

    def test_node_data_immutable(self):
        """Test that node data is immutable."""
        lumber = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        node = NodeData(lumber_piece=lumber)

        with pytest.raises(AttributeError):
            node.local_position = (1.0, 2.0, 3.0)


class TestEdgeData:
    """Test EdgeData dataclass."""

    def test_edge_data_creation(self):
        """Test creating edge data."""
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )
        edge = EdgeData(joint=joint)

        assert edge.joint == joint
        assert edge.assembly_order is None

    def test_edge_data_with_order(self):
        """Test edge data with assembly order."""
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )
        edge = EdgeData(joint=joint, assembly_order=3)

        assert edge.assembly_order == 3


class TestWoodworkingGraph:
    """Test WoodworkingGraph class."""

    def test_graph_creation(self):
        """Test creating an empty graph."""
        graph = WoodworkingGraph()

        assert isinstance(graph._graph, nx.MultiDiGraph)
        assert graph.node_count() == 0
        assert graph.edge_count() == 0

    def test_add_lumber_piece(self):
        """Test adding lumber pieces as nodes."""
        graph = WoodworkingGraph()
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 800.0)

        # Add first piece at origin
        graph.add_lumber_piece(lumber1)
        assert graph.node_count() == 1
        assert graph.has_lumber("beam1")

        # Add second piece with transform
        graph.add_lumber_piece(
            lumber2, position=(100.0, 0.0, 0.0), rotation=(0.0, 0.0, 90.0)
        )
        assert graph.node_count() == 2
        assert graph.has_lumber("beam2")

    def test_add_duplicate_lumber(self):
        """Test that adding duplicate lumber raises error."""
        graph = WoodworkingGraph()
        lumber = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber)

        with pytest.raises(ValueError, match="already exists"):
            graph.add_lumber_piece(lumber)

    def test_add_joint(self):
        """Test adding joints as edges."""
        graph = WoodworkingGraph()
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2, position=(100.0, 0.0, 0.0))

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        graph.add_joint("beam1", "beam2", joint)

        assert graph.edge_count() == 1
        assert graph.has_joint("beam1", "beam2")

    def test_add_joint_missing_lumber(self):
        """Test adding joint with missing lumber raises error."""
        graph = WoodworkingGraph()
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(lumber1)

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        with pytest.raises(ValueError, match="not found"):
            graph.add_joint("beam1", "beam2", joint)

    def test_get_lumber_data(self):
        """Test retrieving lumber node data."""
        graph = WoodworkingGraph()
        lumber = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(lumber, position=(10.0, 20.0, 30.0))

        node_data = graph.get_lumber_data("beam1")
        assert node_data.lumber_piece == lumber
        assert node_data.local_position == (10.0, 20.0, 30.0)

    def test_get_joint_data(self):
        """Test retrieving joint edge data."""
        graph = WoodworkingGraph()
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        graph.add_joint("beam1", "beam2", joint, assembly_order=2)

        edge_data = graph.get_joint_data("beam1", "beam2")
        assert edge_data.joint == joint
        assert edge_data.assembly_order == 2

    def test_get_neighbors(self):
        """Test getting connected lumber pieces."""
        graph = WoodworkingGraph()

        # Create a simple structure: beam1 -- beam2 -- beam3
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)
        lumber3 = LumberPiece("beam3", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)
        graph.add_lumber_piece(lumber3)

        joint1 = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )
        joint2 = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        graph.add_joint("beam1", "beam2", joint1)
        graph.add_joint("beam2", "beam3", joint2)

        # Check neighbors
        beam1_neighbors = graph.get_neighbors("beam1")
        assert len(beam1_neighbors) == 1
        assert "beam2" in beam1_neighbors

        beam2_neighbors = graph.get_neighbors("beam2")
        assert len(beam2_neighbors) == 2
        assert "beam1" in beam2_neighbors
        assert "beam3" in beam2_neighbors

    def test_multiple_joints_between_pieces(self):
        """Test multiple joints between same pieces."""
        graph = WoodworkingGraph()
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)

        # Add two joints at different positions
        joint1 = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.25),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.25),
        )
        joint2 = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.75),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.75),
        )

        graph.add_joint("beam1", "beam2", joint1)
        graph.add_joint("beam1", "beam2", joint2)

        # Should have 2 edges between the nodes
        joints = graph.get_all_joints("beam1", "beam2")
        assert len(joints) == 2


class TestGraphTraversal:
    """Test graph traversal and world coordinate calculation."""

    def test_calculate_world_position_single_node(self):
        """Test world position for single node."""
        graph = WoodworkingGraph()
        lumber = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(lumber, position=(100.0, 50.0, 0.0))

        world_pos = calculate_world_position(graph, "beam1")
        assert world_pos == (100.0, 50.0, 0.0)

    def test_calculate_world_position_chain(self):
        """Test world position through connected pieces."""
        graph = WoodworkingGraph()

        # Create chain: origin -> beam1 -> beam2
        origin = LumberPiece("origin", LumberType.LUMBER_2X4, 1000.0)
        beam1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        beam2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(origin)  # at (0, 0, 0)
        graph.add_lumber_piece(beam1, position=(1000.0, 0.0, 0.0))
        graph.add_lumber_piece(beam2, position=(1000.0, 0.0, 0.0))

        # Connect them
        joint1 = AlignedScrewJoint(
            src_face=Face.FRONT,
            dst_face=Face.BACK,
            src_edge_point=EdgePoint(Face.FRONT, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.BACK, Face.RIGHT, 0.5),
        )
        joint2 = AlignedScrewJoint(
            src_face=Face.FRONT,
            dst_face=Face.BACK,
            src_edge_point=EdgePoint(Face.FRONT, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.BACK, Face.RIGHT, 0.5),
        )

        graph.add_joint("origin", "beam1", joint1)
        graph.add_joint("beam1", "beam2", joint2)

        # Calculate world positions
        origin_pos = calculate_world_position(graph, "origin")
        beam1_pos = calculate_world_position(graph, "beam1", origin_id="origin")
        beam2_pos = calculate_world_position(graph, "beam2", origin_id="origin")

        assert origin_pos == (0.0, 0.0, 0.0)
        assert beam1_pos == (1000.0, 0.0, 0.0)
        assert beam2_pos == (2000.0, 0.0, 0.0)

    def test_calculate_world_rotation(self):
        """Test world rotation calculation."""
        graph = WoodworkingGraph()

        origin = LumberPiece("origin", LumberType.LUMBER_2X4, 1000.0)
        beam1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(origin)
        graph.add_lumber_piece(beam1, rotation=(0.0, 0.0, 90.0))

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )
        graph.add_joint("origin", "beam1", joint)

        # Get world rotation
        rotation = calculate_world_rotation(graph, "beam1", origin_id="origin")
        assert rotation == (0.0, 0.0, 90.0)


class TestFunctionalHelpers:
    """Test functional helper functions."""

    def test_create_lumber_node(self):
        """Test lumber node creation helper."""
        lumber = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        node = create_lumber_node(lumber, position=(10.0, 20.0, 30.0))

        assert isinstance(node, NodeData)
        assert node.lumber_piece == lumber
        assert node.local_position == (10.0, 20.0, 30.0)

    def test_create_joint_edge(self):
        """Test joint edge creation helper."""
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )
        edge = create_joint_edge(joint, assembly_order=5)

        assert isinstance(edge, EdgeData)
        assert edge.joint == joint
        assert edge.assembly_order == 5


class TestErrorHandling:
    """Test error handling for edge cases."""

    def test_get_lumber_data_not_found(self):
        """Test getting data for non-existent lumber."""
        graph = WoodworkingGraph()

        with pytest.raises(KeyError, match="not found"):
            graph.get_lumber_data("nonexistent")

    def test_add_joint_missing_source(self):
        """Test adding joint with missing source lumber."""
        graph = WoodworkingGraph()
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(lumber2)

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        # Test missing source
        with pytest.raises(ValueError, match="Source lumber 'beam1' not found"):
            graph.add_joint("beam1", "beam2", joint)

    def test_add_joint_missing_destination(self):
        """Test adding joint with missing destination lumber."""
        graph = WoodworkingGraph()
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(lumber1)

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        # Test missing destination
        with pytest.raises(ValueError, match="Destination lumber 'beam2' not found"):
            graph.add_joint("beam1", "beam2", joint)

    def test_get_joint_data_not_found(self):
        """Test getting joint data when no joint exists."""
        graph = WoodworkingGraph()
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)

        with pytest.raises(KeyError, match="No joint found"):
            graph.get_joint_data("beam1", "beam2")

    def test_get_all_joints_empty(self):
        """Test getting all joints when none exist."""
        graph = WoodworkingGraph()
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)

        joints = graph.get_all_joints("beam1", "beam2")
        assert joints == []

    def test_get_neighbors_not_found(self):
        """Test getting neighbors for non-existent lumber."""
        graph = WoodworkingGraph()

        neighbors = graph.get_neighbors("nonexistent")
        assert neighbors == []

    def test_calculate_world_position_no_path(self):
        """Test world position calculation when no path exists."""
        graph = WoodworkingGraph()

        # Create disconnected pieces
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)

        graph.add_lumber_piece(lumber1, position=(100.0, 0.0, 0.0))
        graph.add_lumber_piece(lumber2, position=(200.0, 0.0, 0.0))

        # No path between beam1 and beam2
        pos = calculate_world_position(graph, "beam2", origin_id="beam1")
        # Should return local position when no path exists
        assert pos == (200.0, 0.0, 0.0)

    def test_calculate_world_rotation_same_node(self):
        """Test world rotation when origin is same as target."""
        graph = WoodworkingGraph()
        lumber = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(lumber, rotation=(45.0, 0.0, 0.0))

        rotation = calculate_world_rotation(graph, "beam1", origin_id="beam1")
        assert rotation == (45.0, 0.0, 0.0)
