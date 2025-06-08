"""Property-based tests for graph invariants using hypothesis."""

from hypothesis import given, strategies as st, assume, settings, HealthCheck
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, initialize

from nichiyou_daiku.graph.woodworking_graph import WoodworkingGraph
from nichiyou_daiku.core.lumber import LumberPiece, LumberType, Face
from nichiyou_daiku.core.geometry import EdgePoint
from nichiyou_daiku.connectors.aligned_screw import AlignedScrewJoint


# Strategies for generating test data
lumber_types = st.sampled_from(list(LumberType))
faces = st.sampled_from(list(Face))
lumber_lengths = st.floats(min_value=100.0, max_value=5000.0)
edge_positions = st.floats(min_value=0.0, max_value=1.0)
lumber_ids = st.text(
    min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz0123456789_"
)


@st.composite
def lumber_piece(draw):
    """Generate a random lumber piece."""
    return LumberPiece(
        id=draw(lumber_ids), lumber_type=draw(lumber_types), length=draw(lumber_lengths)
    )


@st.composite
def edge_point(draw):
    """Generate a random edge point."""
    face = draw(faces)
    adjacent_face = draw(faces)
    assume(face != adjacent_face)  # Face can't be adjacent to itself
    position = draw(edge_positions)
    return EdgePoint(face, adjacent_face, position)


@st.composite
def aligned_screw_joint(draw):
    """Generate a random aligned screw joint."""
    return AlignedScrewJoint(
        src_face=draw(faces),
        dst_face=draw(faces),
        src_edge_point=draw(edge_point()),
        dst_edge_point=draw(edge_point()),
    )


class TestGraphProperties:
    """Test fundamental graph properties that should always hold."""

    @given(
        pieces=st.lists(
            lumber_piece(), min_size=1, max_size=10, unique_by=lambda p: p.id
        )
    )
    def test_node_count_consistency(self, pieces):
        """Node count should always equal number of unique pieces added."""
        graph = WoodworkingGraph()

        for piece in pieces:
            graph.add_lumber_piece(piece)

        assert graph.node_count() == len(pieces)

        # All pieces should be retrievable
        for piece in pieces:
            assert graph.has_lumber(piece.id)
            assert graph.get_lumber_data(piece.id).lumber_piece == piece

    @given(
        pieces=st.lists(
            lumber_piece(), min_size=2, max_size=5, unique_by=lambda p: p.id
        ),
        joints=st.lists(aligned_screw_joint(), min_size=1, max_size=10),
    )
    @settings(suppress_health_check=[HealthCheck.filter_too_much])
    def test_edge_symmetry(self, pieces, joints):
        """Edges should maintain symmetry in directed graph."""
        graph = WoodworkingGraph()

        # Add pieces
        for piece in pieces:
            graph.add_lumber_piece(piece)

        # Add joints between random pairs
        edge_count = 0
        for i, joint in enumerate(joints):
            src_idx = i % len(pieces)
            dst_idx = (i + 1) % len(pieces)
            src = pieces[src_idx].id
            dst = pieces[dst_idx].id

            if src != dst:  # No self-loops
                graph.add_joint(src, dst, joint)
                edge_count += 1

        # Verify edge count
        assert graph.edge_count() == edge_count

        # Verify all edges exist
        for i, joint in enumerate(joints[:edge_count]):
            src_idx = i % len(pieces)
            dst_idx = (i + 1) % len(pieces)
            src = pieces[src_idx].id
            dst = pieces[dst_idx].id

            if src != dst:
                assert graph.has_joint(src, dst)

    @given(
        pieces=st.lists(
            lumber_piece(), min_size=3, max_size=10, unique_by=lambda p: p.id
        )
    )
    def test_path_transitivity(self, pieces):
        """If path exists from A to B and B to C, path should exist from A to C."""
        graph = WoodworkingGraph()

        # Add all pieces
        for piece in pieces:
            graph.add_lumber_piece(piece)

        # Create a chain
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        for i in range(len(pieces) - 1):
            graph.add_joint(pieces[i].id, pieces[i + 1].id, joint)

        # Test transitivity
        for i in range(len(pieces)):
            for j in range(i + 1, len(pieces)):
                path = graph.find_path(pieces[i].id, pieces[j].id)
                assert path is not None
                assert len(path) == j - i + 1
                assert path[0] == pieces[i].id
                assert path[-1] == pieces[j].id

    @given(
        pieces=st.lists(
            lumber_piece(), min_size=2, max_size=20, unique_by=lambda p: p.id
        )
    )
    def test_connected_components_partition(self, pieces):
        """Connected components should form a partition of all nodes."""
        graph = WoodworkingGraph()

        # Add all pieces
        for piece in pieces:
            graph.add_lumber_piece(piece)

        # Add some connections to create components
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        # Connect pieces in groups
        group_size = 3
        for i in range(0, len(pieces) - 1, group_size):
            for j in range(i, min(i + group_size - 1, len(pieces) - 1)):
                graph.add_joint(pieces[j].id, pieces[j + 1].id, joint)

        # Get components
        components = graph.get_connected_components()

        # Verify partition properties
        all_nodes = set()
        for component in components:
            # No duplicates within component
            assert len(component) == len(set(component))
            all_nodes.update(component)

        # All nodes covered exactly once
        assert all_nodes == {p.id for p in pieces}

    @given(
        graph1_pieces=st.lists(
            lumber_piece(), min_size=1, max_size=5, unique_by=lambda p: p.id
        ),
        graph2_pieces=st.lists(
            lumber_piece(), min_size=1, max_size=5, unique_by=lambda p: p.id
        ),
    )
    def test_merge_preserves_structure(self, graph1_pieces, graph2_pieces):
        """Merging graphs should preserve all nodes and edges."""
        # Ensure no ID conflicts
        assume(all(p1.id != p2.id for p1 in graph1_pieces for p2 in graph2_pieces))

        graph1 = WoodworkingGraph()
        graph2 = WoodworkingGraph()

        # Build first graph
        for piece in graph1_pieces:
            graph1.add_lumber_piece(piece)

        # Build second graph
        for piece in graph2_pieces:
            graph2.add_lumber_piece(piece)

        # Record original counts
        original_nodes1 = graph1.node_count()
        original_nodes2 = graph2.node_count()

        # Merge
        graph1.merge_graph(graph2)

        # Verify preservation
        assert graph1.node_count() == original_nodes1 + original_nodes2

        # All pieces should exist
        for piece in graph1_pieces + graph2_pieces:
            assert graph1.has_lumber(piece.id)


class TestGraphInvariants:
    """Test invariants that should hold after any sequence of operations."""

    # TODO: Uncomment when remove_lumber_piece is implemented
    # @given(
    #     operations=st.lists(
    #         st.one_of(
    #             st.tuples(st.just("add"), lumber_piece()),
    #             st.tuples(st.just("remove"), lumber_ids),
    #             st.tuples(
    #                 st.just("joint"), lumber_ids, lumber_ids, aligned_screw_joint()
    #             ),
    #         ),
    #         min_size=1,
    #         max_size=20,
    #     )
    # )
    # def test_graph_consistency_under_operations(self, operations):
    #     """Graph should remain consistent under any sequence of valid operations."""
    #     graph = WoodworkingGraph()
    #     existing_ids = set()

    #     for op in operations:
    #         if op[0] == "add":
    #             piece = op[1]
    #             if piece.id not in existing_ids:
    #                 graph.add_lumber_piece(piece)
    #                 existing_ids.add(piece.id)

    #         elif op[0] == "remove":
    #             piece_id = op[1]
    #             if piece_id in existing_ids:
    #                 graph.remove_lumber_piece(piece_id)
    #                 existing_ids.remove(piece_id)

    #         elif op[0] == "joint":
    #             src, dst, joint = op[1], op[2], op[3]
    #             if src in existing_ids and dst in existing_ids and src != dst:
    #                 graph.add_joint(src, dst, joint)

    #         # Invariants after each operation
    #         assert graph.node_count() == len(existing_ids)
    #         assert all(graph.has_lumber(id) for id in existing_ids)
    #         assert not any(
    #             graph.has_lumber(id) for id in set(graph._graph.nodes()) - existing_ids
    #         )

    @given(
        pieces=st.lists(
            lumber_piece(), min_size=5, max_size=10, unique_by=lambda p: p.id
        )
    )
    def test_subgraph_properties(self, pieces):
        """Subgraphs should maintain graph properties."""
        graph = WoodworkingGraph()

        # Build a connected graph
        for piece in pieces:
            graph.add_lumber_piece(piece)

        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        # Connect in a chain
        for i in range(len(pieces) - 1):
            graph.add_joint(pieces[i].id, pieces[i + 1].id, joint)

        # Extract random subgraph
        import random

        subgraph_size = random.randint(2, len(pieces) - 1)
        subgraph_nodes = [p.id for p in random.sample(pieces, subgraph_size)]

        subgraph = graph.extract_subgraph(subgraph_nodes)

        # Properties
        assert subgraph.node_count() == len(subgraph_nodes)
        assert all(subgraph.has_lumber(id) for id in subgraph_nodes)

        # Edges should only connect nodes in subgraph
        for src, dst in subgraph._graph.edges():
            assert src in subgraph_nodes
            assert dst in subgraph_nodes


class GraphStateMachine(RuleBasedStateMachine):
    """Stateful testing of graph operations."""

    def __init__(self):
        super().__init__()
        self.graph = WoodworkingGraph()
        self.pieces = {}  # id -> LumberPiece
        self.joints = []  # List of (src, dst, joint) tuples

    @initialize()
    def setup(self):
        """Initialize with some pieces."""
        # Start with a few pieces
        for i in range(3):
            piece = LumberPiece(f"initial_{i}", LumberType.LUMBER_2X4, 1000.0)
            self.graph.add_lumber_piece(piece)
            self.pieces[piece.id] = piece

    @rule(piece=lumber_piece())
    def add_piece(self, piece):
        """Add a new lumber piece."""
        if piece.id not in self.pieces:
            self.graph.add_lumber_piece(piece)
            self.pieces[piece.id] = piece

    @rule(
        src=lumber_ids,
        dst=lumber_ids,
        joint=aligned_screw_joint(),
    )
    def add_joint(self, src, dst, joint):
        """Add a joint between existing pieces."""
        if src and dst and src != dst and src in self.pieces and dst in self.pieces:
            self.graph.add_joint(src, dst, joint)
            self.joints.append((src, dst, joint))

    # TODO: Uncomment when remove_lumber_piece is implemented
    # @rule(
    #     piece_id=st.sampled_from(
    #         lambda self: list(self.pieces.keys()) if self.pieces else []
    #     )
    # )
    # def remove_piece(self, piece_id):
    #     """Remove a piece and its joints."""
    #     if piece_id and piece_id in self.pieces:
    #         self.graph.remove_lumber_piece(piece_id)
    #         del self.pieces[piece_id]
    #         # Remove joints involving this piece
    #         self.joints = [
    #             (s, d, j) for s, d, j in self.joints if s != piece_id and d != piece_id
    #         ]

    @invariant()
    def node_count_matches(self):
        """Node count should match our tracking."""
        assert self.graph.node_count() == len(self.pieces)

    @invariant()
    def all_pieces_exist(self):
        """All tracked pieces should exist in graph."""
        for piece_id in self.pieces:
            assert self.graph.has_lumber(piece_id)

    @invariant()
    def components_valid(self):
        """Connected components should partition the graph."""
        components = self.graph.get_connected_components()
        all_nodes = set()
        for component in components:
            all_nodes.update(component)
        assert all_nodes == set(self.pieces.keys())


# Run the state machine tests
TestGraphStateMachine = GraphStateMachine.TestCase


class TestPropertyBasedValidation:
    """Property-based tests for validation logic."""

    @given(
        num_pieces=st.integers(min_value=2, max_value=10),
        connectivity=st.floats(min_value=0.0, max_value=1.0),
    )
    def test_connectivity_validation_properties(self, num_pieces, connectivity):
        """Connectivity validation should correctly identify disconnected graphs."""
        from nichiyou_daiku.graph.validation import (
            ConnectivityValidator,
            ValidationMode,
            ValidationSuccess,
            ValidationError,
        )

        graph = WoodworkingGraph()

        # Add pieces
        pieces = []
        for i in range(num_pieces):
            piece = LumberPiece(f"beam{i}", LumberType.LUMBER_2X4, 1000.0)
            pieces.append(piece)
            graph.add_lumber_piece(piece)

        # Add connections based on connectivity factor
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        import random

        random.seed(42)  # Deterministic for property

        num_connections = int(connectivity * num_pieces * (num_pieces - 1) / 2)
        connections_made = 0

        for i in range(num_pieces):
            for j in range(i + 1, num_pieces):
                if connections_made < num_connections:
                    if random.random() < connectivity:
                        graph.add_joint(pieces[i].id, pieces[j].id, joint)
                        connections_made += 1

        # Validate
        validator = ConnectivityValidator()
        result = validator.validate(graph, ValidationMode.STRICT)

        # High connectivity should pass, low should fail
        components = graph.get_connected_components()
        if len(components) == 1:
            assert isinstance(result, ValidationSuccess)
        else:
            assert isinstance(result, ValidationError)
            assert result.has_errors

    @given(
        pieces=st.lists(
            lumber_piece(), min_size=2, max_size=5, unique_by=lambda p: p.id
        ),
        assembly_orders=st.lists(
            st.integers(min_value=1, max_value=10), min_size=1, max_size=10
        ),
    )
    def test_assembly_order_validation_properties(self, pieces, assembly_orders):
        """Assembly order validation should detect gaps and duplicates."""
        from nichiyou_daiku.graph.validation import (
            AssemblyOrderValidator,
            ValidationMode,
        )

        graph = WoodworkingGraph()

        # Add pieces
        for piece in pieces:
            graph.add_lumber_piece(piece)

        # Add joints with assembly orders
        joint = AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        )

        orders_used = []
        for i, order in enumerate(assembly_orders[: len(pieces) - 1]):
            src_idx = i % len(pieces)
            dst_idx = (i + 1) % len(pieces)
            if pieces[src_idx].id != pieces[dst_idx].id:
                graph.add_joint(
                    pieces[src_idx].id, pieces[dst_idx].id, joint, assembly_order=order
                )
                orders_used.append(order)

        # Validate
        validator = AssemblyOrderValidator()
        result = validator.validate(graph, ValidationMode.STRICT)

        # Check for gaps
        if orders_used:
            sorted_orders = sorted(set(orders_used))
            has_gaps = any(
                sorted_orders[i + 1] - sorted_orders[i] > 1
                for i in range(len(sorted_orders) - 1)
            )
            has_duplicates = len(orders_used) != len(set(orders_used))

            if has_gaps or has_duplicates:
                assert result.has_errors or result.warning_count > 0
