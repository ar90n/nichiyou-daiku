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
    calculate_piece_origin_position,
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

    def test_node_data_immutable(self):
        """Test that node data is immutable."""
        lumber = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        node = NodeData(lumber_piece=lumber)

        with pytest.raises(AttributeError):
            node.lumber_piece = LumberPiece("other", LumberType.LUMBER_2X4, 500.0)


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

        # Add pieces
        graph.add_lumber_piece(lumber1)
        assert graph.node_count() == 1
        assert graph.has_lumber("beam1")

        graph.add_lumber_piece(lumber2)
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
        graph.add_lumber_piece(lumber2)

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
        graph.add_lumber_piece(lumber)

        node_data = graph.get_lumber_data("beam1")
        assert node_data.lumber_piece == lumber

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

    def test_calculate_piece_origin_single_node(self):
        """Test origin position for single node."""
        graph = WoodworkingGraph()
        lumber = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(lumber)

        # Single node at graph origin
        origin_pos = calculate_piece_origin_position(graph, "beam1")
        assert origin_pos == (0.0, 0.0, 0.0)

    def test_calculate_world_position_face_center(self):
        """Test calculating world position of a face center."""
        graph = WoodworkingGraph()
        lumber = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(lumber)

        # Get TOP face center position
        # For a 2x4 (width=38mm, height=89mm, length=1000mm)
        # Local coordinates are relative to piece center, not origin
        # TOP face center local: (0, 0, 44.5) - half of height above center
        top_center = calculate_world_position(graph, "beam1", Face.TOP)
        assert top_center == (0.0, 0.0, 44.5)

        # Get BOTTOM face center
        # BOTTOM face center local: (0, 0, -44.5) - half of height below center
        bottom_center = calculate_world_position(graph, "beam1", Face.BOTTOM)
        assert bottom_center == (0.0, 0.0, -44.5)

    def test_calculate_world_position_connected_pieces(self):
        """Test world position calculation through joints."""
        graph = WoodworkingGraph()

        # Create two 2x4s connected end-to-end
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 800.0)

        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)

        # Connect at FRONT face of beam1 to BACK face of beam2
        joint = AlignedScrewJoint(
            src_face=Face.FRONT,
            dst_face=Face.BACK,
            src_edge_point=EdgePoint(Face.FRONT, Face.TOP, 0.5),
            dst_edge_point=EdgePoint(Face.BACK, Face.TOP, 0.5),
        )

        graph.add_joint("beam1", "beam2", joint)

        # beam2 origin should be at x=1000 (end of beam1)
        beam2_origin = calculate_piece_origin_position(
            graph, "beam2", origin_id="beam1"
        )
        assert beam2_origin == (1000.0, 0.0, 0.0)

        # beam2 TOP face center should be at its center position
        beam2_top = calculate_world_position(
            graph, "beam2", Face.TOP, origin_id="beam1"
        )
        # beam2 center is at x=1400 (origin 1000 + half-length 400)
        # TOP face local offset is (0, 0, 44.5)
        # So world position is (1400, 19, 89)
        assert beam2_top == (1400.0, 19.0, 89.0)


class TestFunctionalHelpers:
    """Test functional helper functions."""

    def test_create_lumber_node(self):
        """Test lumber node creation helper."""
        lumber = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        node = create_lumber_node(lumber)

        assert isinstance(node, NodeData)
        assert node.lumber_piece == lumber

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
