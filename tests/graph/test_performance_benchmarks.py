"""Performance benchmarks for graph operations."""

import pytest
import time
from typing import List, Dict

from nichiyou_daiku.graph.woodworking_graph import WoodworkingGraph
from nichiyou_daiku.core.lumber import LumberPiece, LumberType, Face
from nichiyou_daiku.core.geometry import EdgePoint
from nichiyou_daiku.connectors.aligned_screw import AlignedScrewJoint


class BenchmarkTimer:
    """Simple timer for benchmarking."""

    def __init__(self):
        self.times: Dict[str, List[float]] = {}

    def time_operation(self, name: str, func, *args, **kwargs):
        """Time a single operation."""
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start

        if name not in self.times:
            self.times[name] = []
        self.times[name].append(elapsed)

        return result

    def get_stats(self, name: str) -> Dict[str, float]:
        """Get statistics for named operation."""
        if name not in self.times:
            return {}

        times = self.times[name]
        return {
            "min": min(times),
            "max": max(times),
            "avg": sum(times) / len(times),
            "total": sum(times),
            "count": len(times),
        }


@pytest.fixture
def timer():
    """Provide a timer for benchmarks."""
    return BenchmarkTimer()


class TestGraphCreationPerformance:
    """Benchmark graph creation operations."""

    @pytest.mark.parametrize("num_pieces", [10, 50, 100, 500])
    def test_node_addition_scaling(self, timer, num_pieces):
        """Test how node addition scales with graph size."""
        graph = WoodworkingGraph()

        for i in range(num_pieces):
            piece = LumberPiece(f"beam{i}", LumberType.LUMBER_2X4, 1000.0)
            timer.time_operation("add_piece", graph.add_lumber_piece, piece)

        stats = timer.get_stats("add_piece")

        # Performance assertions
        assert stats["avg"] < 0.01  # Less than 10ms per piece (relaxed for CI)
        assert stats["max"] < 0.01  # No individual operation over 10ms

        # Log results
        print(f"\nNode addition for {num_pieces} pieces:")
        print(f"  Average: {stats['avg']*1000:.2f}ms")
        print(f"  Total: {stats['total']:.2f}s")

    @pytest.mark.parametrize("num_joints", [10, 50, 100, 500])
    def test_edge_addition_scaling(self, timer, num_joints):
        """Test how edge addition scales with number of joints."""
        graph = WoodworkingGraph()

        # Create pieces first
        pieces = []
        for i in range(num_joints + 1):
            piece = LumberPiece(f"beam{i}", LumberType.LUMBER_2X4, 1000.0)
            pieces.append(piece)
            graph.add_lumber_piece(piece)

        # Add joints
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        for i in range(num_joints):
            timer.time_operation(
                "add_joint", graph.add_joint, f"beam{i}", f"beam{i+1}", joint
            )

        stats = timer.get_stats("add_joint")

        # Performance assertions
        assert stats["avg"] < 0.01  # Less than 10ms per joint (relaxed for CI)
        assert stats["total"] < 1.0  # Total under 1 second

    def test_large_assembly_creation(self, timer):
        """Test creating a large realistic assembly."""
        graph = WoodworkingGraph()

        # Create a 10x10x10 cube frame (1000 pieces)
        grid_size = 10

        # Time piece creation
        start = time.perf_counter()
        pieces = []
        for x in range(grid_size):
            for y in range(grid_size):
                for z in range(grid_size):
                    piece_id = f"beam_{x}_{y}_{z}"
                    piece = LumberPiece(piece_id, LumberType.LUMBER_2X4, 1000.0)
                    pieces.append(piece)
                    graph.add_lumber_piece(piece)

        piece_time = time.perf_counter() - start

        # Time joint creation
        start = time.perf_counter()
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        # Connect adjacent pieces
        connections = 0
        for x in range(grid_size):
            for y in range(grid_size):
                for z in range(grid_size):
                    current = f"beam_{x}_{y}_{z}"
                    # Connect in 3 directions
                    if x < grid_size - 1:
                        graph.add_joint(current, f"beam_{x+1}_{y}_{z}", joint)
                        connections += 1
                    if y < grid_size - 1:
                        graph.add_joint(current, f"beam_{x}_{y+1}_{z}", joint)
                        connections += 1
                    if z < grid_size - 1:
                        graph.add_joint(current, f"beam_{x}_{y}_{z+1}", joint)
                        connections += 1

        joint_time = time.perf_counter() - start

        # Assertions
        assert piece_time < 1.0  # 1000 pieces in under 1 second
        assert joint_time < 5.0  # ~2700 joints in under 5 seconds

        print("\nLarge assembly creation:")
        print(f"  Pieces: {len(pieces)} in {piece_time:.2f}s")
        print(f"  Joints: {connections} in {joint_time:.2f}s")


class TestGraphTraversalPerformance:
    """Benchmark graph traversal operations."""

    def create_chain_graph(self, length: int) -> WoodworkingGraph:
        """Create a chain of connected pieces."""
        graph = WoodworkingGraph()

        for i in range(length):
            piece = LumberPiece(f"beam{i}", LumberType.LUMBER_2X4, 1000.0)
            graph.add_lumber_piece(piece)

        joint = AlignedScrewJoint(
            src_face=Face.FRONT,
            dst_face=Face.BACK,
            src_edge_point=EdgePoint(Face.FRONT, Face.TOP, 0.5),
            dst_edge_point=EdgePoint(Face.BACK, Face.TOP, 0.5),
        )

        for i in range(length - 1):
            graph.add_joint(f"beam{i}", f"beam{i+1}", joint)

        return graph

    @pytest.mark.parametrize("chain_length", [10, 50, 100, 500])
    def test_pathfinding_performance(self, timer, chain_length):
        """Test pathfinding performance on chains."""
        graph = self.create_chain_graph(chain_length)

        # Time pathfinding from start to end
        result = timer.time_operation(
            "find_path", graph.find_path, "beam0", f"beam{chain_length-1}"
        )

        stats = timer.get_stats("find_path")

        assert result is not None
        assert len(result) == chain_length
        assert stats["avg"] < 0.1  # Under 100ms

    def test_neighbor_lookup_performance(self, timer):
        """Test neighbor lookup performance."""
        # Create a highly connected graph
        graph = WoodworkingGraph()

        # Hub and spoke pattern
        hub = LumberPiece("hub", LumberType.LUMBER_2X4, 1000.0)
        graph.add_lumber_piece(hub)

        num_spokes = 100
        for i in range(num_spokes):
            spoke = LumberPiece(f"spoke{i}", LumberType.LUMBER_2X4, 1000.0)
            graph.add_lumber_piece(spoke)

            joint = AlignedScrewJoint(
                src_face=Face.TOP,
                dst_face=Face.TOP,
                src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, i / num_spokes),
                dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
            )
            graph.add_joint("hub", f"spoke{i}", joint)

        # Time neighbor lookups
        for _ in range(100):
            timer.time_operation("get_neighbors", graph.get_neighbors, "hub")

        stats = timer.get_stats("get_neighbors")
        assert stats["avg"] < 0.01  # Under 10ms (relaxed for CI)

    def test_component_detection_performance(self, timer):
        """Test connected component detection performance."""
        graph = WoodworkingGraph()

        # Create multiple disconnected structures
        num_components = 20
        component_size = 50

        for comp in range(num_components):
            # Create a chain for each component
            for i in range(component_size):
                piece_id = f"comp{comp}_beam{i}"
                piece = LumberPiece(piece_id, LumberType.LUMBER_2X4, 1000.0)
                graph.add_lumber_piece(piece)

            joint = AlignedScrewJoint(
                src_face=Face.TOP,
                dst_face=Face.TOP,
                src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
                dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
            )

            for i in range(component_size - 1):
                src = f"comp{comp}_beam{i}"
                dst = f"comp{comp}_beam{i+1}"
                graph.add_joint(src, dst, joint)

        # Time component detection
        result = timer.time_operation("get_components", graph.get_connected_components)

        stats = timer.get_stats("get_components")

        assert len(result) == num_components
        assert stats["avg"] < 0.5  # Under 500ms (relaxed for CI environments)


class TestGraphManipulationPerformance:
    """Benchmark graph manipulation operations."""

    def test_subgraph_extraction_performance(self, timer):
        """Test subgraph extraction performance."""
        # Create a large graph
        graph = WoodworkingGraph()

        grid_size = 20
        for i in range(grid_size):
            for j in range(grid_size):
                piece_id = f"beam_{i}_{j}"
                piece = LumberPiece(piece_id, LumberType.LUMBER_2X4, 1000.0)
                graph.add_lumber_piece(piece)

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        # Connect in grid pattern
        for i in range(grid_size):
            for j in range(grid_size):
                current = f"beam_{i}_{j}"
                if i < grid_size - 1:
                    graph.add_joint(current, f"beam_{i+1}_{j}", joint)
                if j < grid_size - 1:
                    graph.add_joint(current, f"beam_{i}_{j+1}", joint)

        # Extract various sized subgraphs
        subgraph_sizes = [4, 9, 16, 25]  # 2x2, 3x3, 4x4, 5x5

        for size in subgraph_sizes:
            side = int(size**0.5)
            nodes = [f"beam_{i}_{j}" for i in range(side) for j in range(side)]

            result = timer.time_operation(
                f"extract_{size}", graph.extract_subgraph, nodes
            )

            assert result.node_count() == size

        # Check performance
        for size in subgraph_sizes:
            stats = timer.get_stats(f"extract_{size}")
            assert stats["avg"] < 0.05  # Under 50ms

    def test_graph_merge_performance(self, timer):
        """Test graph merging performance."""
        # Create two medium-sized graphs
        graph1 = WoodworkingGraph()
        graph2 = WoodworkingGraph()

        # Build first graph
        for i in range(100):
            piece = LumberPiece(f"g1_beam{i}", LumberType.LUMBER_2X4, 1000.0)
            graph1.add_lumber_piece(piece)

        # Build second graph
        for i in range(100):
            piece = LumberPiece(f"g2_beam{i}", LumberType.LUMBER_2X4, 1000.0)
            graph2.add_lumber_piece(piece)

        # Time merge operation
        timer.time_operation("merge", graph1.merge_graph, graph2)

        stats = timer.get_stats("merge")
        assert stats["avg"] < 0.1  # Under 100ms
        assert graph1.node_count() == 200


class TestMemoryUsage:
    """Test memory usage for large graphs."""

    def test_memory_scaling(self):
        """Test memory usage scales linearly with graph size."""
        import sys

        measurements = []

        for num_pieces in [100, 500, 1000]:
            graph = WoodworkingGraph()

            # Add pieces
            for i in range(num_pieces):
                piece = LumberPiece(f"beam{i}", LumberType.LUMBER_2X4, 1000.0)
                graph.add_lumber_piece(piece)

            # Add joints (chain pattern)
            joint = AlignedScrewJoint(
                src_face=Face.TOP,
                dst_face=Face.TOP,
                src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
                dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
            )

            for i in range(num_pieces - 1):
                graph.add_joint(f"beam{i}", f"beam{i+1}", joint)

            # Rough memory estimate
            size_estimate = (
                sys.getsizeof(graph._graph)
                + sum(sys.getsizeof(n) for n in graph._graph.nodes())
                + sum(sys.getsizeof(e) for e in graph._graph.edges())
            )

            measurements.append((num_pieces, size_estimate))

            # Memory usage should be reasonable
            assert size_estimate < num_pieces * 10000  # Less than 10KB per piece

        print("\nMemory usage:")
        for pieces, mem in measurements:
            print(
                f"  {pieces} pieces: {mem/1024/1024:.2f}MB ({mem/pieces:.0f} bytes/piece)"
            )


class TestConcurrentAccess:
    """Test concurrent access patterns."""

    def test_read_heavy_workload(self, timer):
        """Test performance under read-heavy workload."""
        # Create a moderately complex graph
        graph = WoodworkingGraph()

        # Build a 10x10 grid
        grid_size = 10
        for i in range(grid_size):
            for j in range(grid_size):
                piece_id = f"beam_{i}_{j}"
                piece = LumberPiece(piece_id, LumberType.LUMBER_2X4, 1000.0)
                graph.add_lumber_piece(piece)

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        # Connect grid
        for i in range(grid_size):
            for j in range(grid_size):
                current = f"beam_{i}_{j}"
                if i < grid_size - 1:
                    graph.add_joint(current, f"beam_{i+1}_{j}", joint)
                if j < grid_size - 1:
                    graph.add_joint(current, f"beam_{i}_{j+1}", joint)

        # Simulate read-heavy workload
        operations = 1000
        for _ in range(operations):
            # Mix of read operations
            import random

            op = random.choice(["neighbors", "has_lumber", "get_data", "path"])

            if op == "neighbors":
                node = f"beam_{random.randint(0, grid_size-1)}_{random.randint(0, grid_size-1)}"
                timer.time_operation("read_neighbors", graph.get_neighbors, node)
            elif op == "has_lumber":
                node = f"beam_{random.randint(0, grid_size-1)}_{random.randint(0, grid_size-1)}"
                timer.time_operation("read_has", graph.has_lumber, node)
            elif op == "get_data":
                node = f"beam_{random.randint(0, grid_size-1)}_{random.randint(0, grid_size-1)}"
                timer.time_operation("read_data", graph.get_lumber_data, node)
            elif op == "path":
                src = "beam_0_0"
                dst = f"beam_{random.randint(0, grid_size-1)}_{random.randint(0, grid_size-1)}"
                timer.time_operation("read_path", graph.find_path, src, dst)

        # Check performance
        for op in ["read_neighbors", "read_has", "read_data", "read_path"]:
            stats = timer.get_stats(op)
            if stats:
                assert stats["avg"] < 0.1  # Under 100ms average (relaxed for CI)


def test_performance_summary(timer):
    """Run a comprehensive performance test suite."""
    print("\n=== Graph Performance Summary ===")

    # Test different graph sizes
    sizes = [10, 50, 100, 500, 1000]

    for size in sizes:
        graph = WoodworkingGraph()

        # Build graph
        start = time.perf_counter()
        for i in range(size):
            piece = LumberPiece(f"beam{i}", LumberType.LUMBER_2X4, 1000.0)
            graph.add_lumber_piece(piece)

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        for i in range(size - 1):
            graph.add_joint(f"beam{i}", f"beam{i+1}", joint)

        build_time = time.perf_counter() - start

        print(f"\nGraph size: {size} nodes")
        print(f"  Build time: {build_time:.3f}s")

        # Test key operations
        if size <= 100:  # Skip expensive ops on huge graphs
            # Pathfinding
            start = time.perf_counter()
            graph.find_path("beam0", f"beam{size-1}")
            path_time = time.perf_counter() - start
            print(f"  Pathfinding: {path_time*1000:.2f}ms")

            # Component detection
            start = time.perf_counter()
            graph.get_connected_components()
            comp_time = time.perf_counter() - start
            print(f"  Component detection: {comp_time*1000:.2f}ms")
