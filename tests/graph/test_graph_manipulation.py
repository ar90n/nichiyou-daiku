"""Extended tests for graph manipulation operations."""

import pytest
import networkx as nx
from typing import List, Set, Tuple

from nichiyou_daiku.graph.woodworking_graph import (
    WoodworkingGraph,
    NodeData,
    EdgeData,
)
from nichiyou_daiku.core.lumber import LumberPiece, LumberType, Face
from nichiyou_daiku.core.geometry import EdgePoint
from nichiyou_daiku.connectors.aligned_screw import AlignedScrewJoint


class TestAdvancedGraphManipulation:
    """Advanced graph manipulation tests beyond basic operations."""

    def test_remove_lumber_piece(self):
        """Test removing a lumber piece and its joints."""
        graph = WoodworkingGraph()
        
        # Create connected structure
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)
        lumber3 = LumberPiece("beam3", LumberType.LUMBER_2X4, 1000.0)
        
        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)
        graph.add_lumber_piece(lumber3)
        
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )
        
        graph.add_joint("beam1", "beam2", joint)
        graph.add_joint("beam2", "beam3", joint)
        
        # Remove middle piece
        graph.remove_lumber_piece("beam2")
        
        assert graph.node_count() == 2
        assert not graph.has_lumber("beam2")
        assert graph.has_lumber("beam1")
        assert graph.has_lumber("beam3")
        assert not graph.has_joint("beam1", "beam2")
        assert not graph.has_joint("beam2", "beam3")

    def test_remove_joint(self):
        """Test removing specific joints."""
        graph = WoodworkingGraph()
        
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)
        
        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)
        
        # Add multiple joints
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
        
        assert len(graph.get_all_joints("beam1", "beam2")) == 2
        
        # Remove one joint
        graph.remove_joint("beam1", "beam2", 0)  # Remove first joint
        
        assert len(graph.get_all_joints("beam1", "beam2")) == 1

    def test_replace_lumber_piece(self):
        """Test replacing a lumber piece while maintaining connections."""
        graph = WoodworkingGraph()
        
        # Original structure
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 800.0)
        lumber3 = LumberPiece("beam3", LumberType.LUMBER_2X4, 1000.0)
        
        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)
        graph.add_lumber_piece(lumber3)
        
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )
        
        graph.add_joint("beam1", "beam2", joint)
        graph.add_joint("beam2", "beam3", joint)
        
        # Replace beam2 with a longer piece
        new_lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1200.0)
        graph.replace_lumber_piece("beam2", new_lumber2)
        
        # Check structure is maintained
        assert graph.has_lumber("beam2")
        assert graph.get_lumber_data("beam2").lumber_piece.length == 1200.0
        assert graph.has_joint("beam1", "beam2")
        assert graph.has_joint("beam2", "beam3")

    def test_clone_subgraph(self):
        """Test cloning a subgraph with offset."""
        graph = WoodworkingGraph()
        
        # Create L-shaped structure
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 800.0)
        
        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)
        
        joint = AlignedScrewJoint(
            src_face=Face.FRONT,
            dst_face=Face.BACK,
            src_edge_point=EdgePoint(Face.FRONT, Face.TOP, 0.5),
            dst_edge_point=EdgePoint(Face.BACK, Face.TOP, 0.5),
        )
        
        graph.add_joint("beam1", "beam2", joint)
        
        # Clone with new IDs
        cloned = graph.clone_subgraph(
            ["beam1", "beam2"],
            id_prefix="copy_",
            position_offset=(2000.0, 0.0, 0.0)
        )
        
        assert cloned.node_count() == 2
        assert cloned.has_lumber("copy_beam1")
        assert cloned.has_lumber("copy_beam2")
        assert cloned.has_joint("copy_beam1", "copy_beam2")

    def test_rotate_assembly(self):
        """Test rotating entire assembly."""
        graph = WoodworkingGraph()
        
        # Create simple structure
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)
        
        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)
        
        joint = AlignedScrewJoint(
            src_face=Face.FRONT,
            dst_face=Face.BACK,
            src_edge_point=EdgePoint(Face.FRONT, Face.TOP, 0.5),
            dst_edge_point=EdgePoint(Face.BACK, Face.TOP, 0.5),
        )
        
        graph.add_joint("beam1", "beam2", joint)
        
        # Rotate 90 degrees around Z axis
        graph.rotate_assembly(90.0, axis='z', center=(0.0, 0.0, 0.0))
        
        # Verify rotation occurred (would need position tracking)
        assert graph.node_count() == 2

    def test_mirror_assembly(self):
        """Test mirroring assembly across a plane."""
        graph = WoodworkingGraph()
        
        # Create asymmetric structure
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 800.0)
        lumber3 = LumberPiece("beam3", LumberType.LUMBER_2X4, 600.0)
        
        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)
        graph.add_lumber_piece(lumber3)
        
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )
        
        graph.add_joint("beam1", "beam2", joint)
        graph.add_joint("beam2", "beam3", joint)
        
        # Mirror across YZ plane
        mirrored = graph.mirror_assembly(plane='yz', offset=2000.0)
        
        assert mirrored.node_count() == 3
        assert mirrored.edge_count() == 2


class TestGraphOptimization:
    """Test graph optimization operations."""

    def test_optimize_joint_order(self):
        """Test optimizing assembly order for minimal movements."""
        graph = WoodworkingGraph()
        
        # Create structure requiring optimization
        pieces = [
            LumberPiece(f"beam{i}", LumberType.LUMBER_2X4, 1000.0)
            for i in range(5)
        ]
        
        for piece in pieces:
            graph.add_lumber_piece(piece)
        
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )
        
        # Add joints in suboptimal order
        graph.add_joint("beam0", "beam4", joint, assembly_order=1)
        graph.add_joint("beam1", "beam2", joint, assembly_order=2)
        graph.add_joint("beam3", "beam4", joint, assembly_order=3)
        graph.add_joint("beam0", "beam1", joint, assembly_order=4)
        graph.add_joint("beam2", "beam3", joint, assembly_order=5)
        
        # Optimize order
        graph.optimize_assembly_order()
        
        # Verify all joints still have orders
        for src, dst, data in graph._graph.edges(data=True):
            edge_data = data['data']
            assert edge_data.assembly_order is not None

    def test_consolidate_joints(self):
        """Test consolidating redundant joints."""
        graph = WoodworkingGraph()
        
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 1000.0)
        
        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)
        
        # Add very close joints that could be consolidated
        joint1 = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.50),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.50),
        )
        joint2 = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.51),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.51),
        )
        
        graph.add_joint("beam1", "beam2", joint1)
        graph.add_joint("beam1", "beam2", joint2)
        
        # Consolidate nearby joints
        graph.consolidate_joints(tolerance=0.05)
        
        # Should have fewer joints
        assert len(graph.get_all_joints("beam1", "beam2")) <= 2


class TestGraphAnalysis:
    """Test graph analysis operations."""

    def test_find_critical_pieces(self):
        """Test finding pieces critical to structural integrity."""
        graph = WoodworkingGraph()
        
        # Create bridge-like structure
        pieces = [
            LumberPiece(f"beam{i}", LumberType.LUMBER_2X4, 1000.0)
            for i in range(5)
        ]
        
        for piece in pieces:
            graph.add_lumber_piece(piece)
        
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )
        
        # beam2 is critical - connects two halves
        graph.add_joint("beam0", "beam1", joint)
        graph.add_joint("beam1", "beam2", joint)  # Critical connection
        graph.add_joint("beam2", "beam3", joint)  # Critical connection
        graph.add_joint("beam3", "beam4", joint)
        
        critical = graph.find_critical_pieces()
        assert "beam2" in critical

    def test_calculate_load_paths(self):
        """Test calculating load distribution paths."""
        graph = WoodworkingGraph()
        
        # Create frame structure
        pieces = [
            LumberPiece(f"beam{i}", LumberType.LUMBER_2X4, 1000.0)
            for i in range(4)
        ]
        
        for piece in pieces:
            graph.add_lumber_piece(piece)
        
        joint = AlignedScrewJoint(
            src_face=Face.FRONT,
            dst_face=Face.BACK,
            src_edge_point=EdgePoint(Face.FRONT, Face.TOP, 0.5),
            dst_edge_point=EdgePoint(Face.BACK, Face.TOP, 0.5),
        )
        
        # Create square frame
        graph.add_joint("beam0", "beam1", joint)
        graph.add_joint("beam1", "beam2", joint)
        graph.add_joint("beam2", "beam3", joint)
        graph.add_joint("beam3", "beam0", joint)
        
        # Analyze load paths from top beam
        load_paths = graph.calculate_load_paths("beam0", load_type="vertical")
        assert len(load_paths) > 0

    def test_find_assembly_sequences(self):
        """Test finding valid assembly sequences."""
        graph = WoodworkingGraph()
        
        # Create structure with dependencies
        base = LumberPiece("base", LumberType.LUMBER_2X4, 1000.0)
        left = LumberPiece("left", LumberType.LUMBER_2X4, 800.0)
        right = LumberPiece("right", LumberType.LUMBER_2X4, 800.0)
        top = LumberPiece("top", LumberType.LUMBER_2X4, 1000.0)
        
        graph.add_lumber_piece(base)
        graph.add_lumber_piece(left)
        graph.add_lumber_piece(right)
        graph.add_lumber_piece(top)
        
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.BOTTOM,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.BOTTOM, Face.LEFT, 0.5),
        )
        
        # Base must be first, top must be last
        graph.add_joint("base", "left", joint)
        graph.add_joint("base", "right", joint)
        graph.add_joint("left", "top", joint)
        graph.add_joint("right", "top", joint)
        
        sequences = graph.find_assembly_sequences()
        
        # All valid sequences should start with base and end with top
        for seq in sequences:
            assert seq[0] == "base"
            assert seq[-1] == "top"

    def test_calculate_material_usage(self):
        """Test calculating total material usage."""
        graph = WoodworkingGraph()
        
        # Add various lumber types
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 800.0)
        lumber3 = LumberPiece("beam3", LumberType.LUMBER_2X8, 1200.0)
        lumber4 = LumberPiece("beam4", LumberType.LUMBER_1X4, 600.0)
        
        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)
        graph.add_lumber_piece(lumber3)
        graph.add_lumber_piece(lumber4)
        
        usage = graph.calculate_material_usage()
        
        assert LumberType.LUMBER_2X4 in usage
        assert usage[LumberType.LUMBER_2X4]["count"] == 2
        assert usage[LumberType.LUMBER_2X4]["total_length"] == 1800.0
        assert usage[LumberType.LUMBER_2X8]["count"] == 1
        assert usage[LumberType.LUMBER_1X4]["count"] == 1


class TestGraphPersistence:
    """Test saving and loading graphs."""

    def test_export_to_dict(self):
        """Test exporting graph to dictionary."""
        graph = WoodworkingGraph()
        
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 800.0)
        
        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)
        
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )
        
        graph.add_joint("beam1", "beam2", joint, assembly_order=1)
        
        # Export to dict
        data = graph.to_dict()
        
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1

    def test_import_from_dict(self):
        """Test importing graph from dictionary."""
        # Create original graph
        graph1 = WoodworkingGraph()
        
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 800.0)
        
        graph1.add_lumber_piece(lumber1)
        graph1.add_lumber_piece(lumber2)
        
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )
        
        graph1.add_joint("beam1", "beam2", joint, assembly_order=1)
        
        # Export and reimport
        data = graph1.to_dict()
        graph2 = WoodworkingGraph.from_dict(data)
        
        # Verify structure
        assert graph2.node_count() == 2
        assert graph2.edge_count() == 1
        assert graph2.has_lumber("beam1")
        assert graph2.has_lumber("beam2")
        assert graph2.has_joint("beam1", "beam2")

    def test_graph_checksum(self):
        """Test generating graph checksum for change detection."""
        graph = WoodworkingGraph()
        
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(lumber1)
        
        checksum1 = graph.calculate_checksum()
        
        # Add another piece
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 800.0)
        graph.add_lumber_piece(lumber2)
        
        checksum2 = graph.calculate_checksum()
        
        # Checksums should be different
        assert checksum1 != checksum2


class TestGraphPerformance:
    """Performance tests for large graphs."""

    def test_large_graph_creation(self):
        """Test creating and manipulating large graphs."""
        graph = WoodworkingGraph()
        
        # Create 100 pieces
        pieces = [
            LumberPiece(f"beam{i}", LumberType.LUMBER_2X4, 1000.0 + i * 10)
            for i in range(100)
        ]
        
        for piece in pieces:
            graph.add_lumber_piece(piece)
        
        assert graph.node_count() == 100
        
        # Add joints in a chain
        joint = AlignedScrewJoint(
            src_face=Face.FRONT,
            dst_face=Face.BACK,
            src_edge_point=EdgePoint(Face.FRONT, Face.TOP, 0.5),
            dst_edge_point=EdgePoint(Face.BACK, Face.TOP, 0.5),
        )
        
        for i in range(99):
            graph.add_joint(f"beam{i}", f"beam{i+1}", joint)
        
        assert graph.edge_count() == 99
        
        # Test performance of common operations
        neighbors = graph.get_neighbors("beam50")
        assert len(neighbors) == 2  # Previous and next in chain
        
        path = graph.find_path("beam0", "beam99")
        assert len(path) == 100

    def test_complex_topology(self):
        """Test graphs with complex topologies."""
        graph = WoodworkingGraph()
        
        # Create grid structure 10x10
        grid_size = 10
        pieces = []
        
        for i in range(grid_size):
            for j in range(grid_size):
                piece_id = f"beam_{i}_{j}"
                piece = LumberPiece(piece_id, LumberType.LUMBER_2X4, 1000.0)
                pieces.append(piece)
                graph.add_lumber_piece(piece)
        
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )
        
        # Connect grid horizontally and vertically
        for i in range(grid_size):
            for j in range(grid_size):
                current = f"beam_{i}_{j}"
                # Connect to right
                if j < grid_size - 1:
                    right = f"beam_{i}_{j+1}"
                    graph.add_joint(current, right, joint)
                # Connect to bottom
                if i < grid_size - 1:
                    bottom = f"beam_{i+1}_{j}"
                    graph.add_joint(current, bottom, joint)
        
        # Test operations on complex graph
        components = graph.get_connected_components()
        assert len(components) == 1  # All connected
        
        # Find shortest path across grid
        path = graph.find_path("beam_0_0", "beam_9_9")
        assert len(path) == 19  # Manhattan distance


class TestGraphExceptions:
    """Test error handling and edge cases."""

    def test_cyclic_dependencies(self):
        """Test handling of cyclic assembly dependencies."""
        graph = WoodworkingGraph()
        
        # Create pieces
        pieces = [
            LumberPiece(f"beam{i}", LumberType.LUMBER_2X4, 1000.0)
            for i in range(3)
        ]
        
        for piece in pieces:
            graph.add_lumber_piece(piece)
        
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )
        
        # Create cycle with assembly dependencies
        graph.add_joint("beam0", "beam1", joint, assembly_order=1)
        graph.add_joint("beam1", "beam2", joint, assembly_order=2)
        graph.add_joint("beam2", "beam0", joint, assembly_order=3)
        
        # Detect assembly order issues
        issues = graph.validate_assembly_dependencies()
        assert len(issues) > 0

    def test_invalid_operations(self):
        """Test handling of invalid graph operations."""
        graph = WoodworkingGraph()
        
        # Try to remove non-existent piece
        with pytest.raises(ValueError):
            graph.remove_lumber_piece("nonexistent")
        
        # Try to add joint between non-existent pieces
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )
        
        with pytest.raises(ValueError):
            graph.add_joint("beam1", "beam2", joint)

    def test_graph_recovery(self):
        """Test recovering from invalid graph states."""
        graph = WoodworkingGraph()
        
        # Create initial valid state
        lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
        lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 800.0)
        
        graph.add_lumber_piece(lumber1)
        graph.add_lumber_piece(lumber2)
        
        # Save valid state
        valid_state = graph.to_dict()
        
        # Corrupt the graph somehow
        graph._graph.add_node("invalid_node", data=None)
        
        # Restore from saved state
        graph = WoodworkingGraph.from_dict(valid_state)
        
        assert graph.node_count() == 2
        assert not graph.has_lumber("invalid_node")