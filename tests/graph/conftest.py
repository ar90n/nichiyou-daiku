"""Shared fixtures for graph tests."""

import pytest

from nichiyou_daiku.graph.woodworking_graph import WoodworkingGraph
from nichiyou_daiku.core.lumber import LumberPiece, LumberType, Face
from nichiyou_daiku.connectors.general import GeneralJoint, JointLocation, JointPose

# Placeholder for old EdgePoint usage
class EdgePoint:
    def __init__(self, face1, face2, position):
        pass

# Helper function to create joints in the old style
def AlignedScrewJoint(src_face, dst_face, src_edge_point, dst_edge_point):
    """Compatibility wrapper to create GeneralJoint from old AlignedScrewJoint parameters."""
    return GeneralJoint(
        base_loc=JointLocation(src_face, 0.0),
        target_loc=JointLocation(dst_face, 0.0),
        target_pose=JointPose(Face.FRONT, Face.TOP)
    )


@pytest.fixture
def empty_graph():
    """Provide an empty woodworking graph."""
    return WoodworkingGraph()


@pytest.fixture
def simple_joint():
    """Provide a simple aligned screw joint."""
    return AlignedScrewJoint(
        src_face=Face.TOP,
        dst_face=Face.TOP,
        src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
        dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
    )


@pytest.fixture
def lumber_2x4_1000():
    """Provide a standard 2x4 lumber piece of 1000mm."""
    return LumberPiece("test_beam", LumberType.LUMBER_2X4, 1000.0)


@pytest.fixture
def three_piece_chain():
    """Provide a graph with three pieces connected in a chain."""
    graph = WoodworkingGraph()

    # Create three pieces
    lumber1 = LumberPiece("beam1", LumberType.LUMBER_2X4, 1000.0)
    lumber2 = LumberPiece("beam2", LumberType.LUMBER_2X4, 800.0)
    lumber3 = LumberPiece("beam3", LumberType.LUMBER_2X4, 1000.0)

    graph.add_lumber_piece(lumber1)
    graph.add_lumber_piece(lumber2)
    graph.add_lumber_piece(lumber3)

    # Connect them in a chain
    joint = AlignedScrewJoint(
        src_face=Face.FRONT,
        dst_face=Face.BACK,
        src_edge_point=EdgePoint(Face.FRONT, Face.TOP, 0.5),
        dst_edge_point=EdgePoint(Face.BACK, Face.TOP, 0.5),
    )

    graph.add_joint("beam1", "beam2", joint, assembly_order=1)
    graph.add_joint("beam2", "beam3", joint, assembly_order=2)

    return graph


@pytest.fixture
def square_frame():
    """Provide a graph forming a square frame."""
    graph = WoodworkingGraph()

    # Create four pieces
    pieces = [
        LumberPiece("top", LumberType.LUMBER_2X4, 1000.0),
        LumberPiece("right", LumberType.LUMBER_2X4, 1000.0),
        LumberPiece("bottom", LumberType.LUMBER_2X4, 1000.0),
        LumberPiece("left", LumberType.LUMBER_2X4, 1000.0),
    ]

    for piece in pieces:
        graph.add_lumber_piece(piece)

    # Connect in a square
    joint = AlignedScrewJoint(
        src_face=Face.FRONT,
        dst_face=Face.BACK,
        src_edge_point=EdgePoint(Face.FRONT, Face.TOP, 0.5),
        dst_edge_point=EdgePoint(Face.BACK, Face.TOP, 0.5),
    )

    graph.add_joint("top", "right", joint, assembly_order=1)
    graph.add_joint("right", "bottom", joint, assembly_order=2)
    graph.add_joint("bottom", "left", joint, assembly_order=3)
    graph.add_joint("left", "top", joint, assembly_order=4)

    return graph


@pytest.fixture
def disconnected_graph():
    """Provide a graph with disconnected components."""
    graph = WoodworkingGraph()

    # Component 1: Two connected pieces
    lumber1 = LumberPiece("comp1_beam1", LumberType.LUMBER_2X4, 1000.0)
    lumber2 = LumberPiece("comp1_beam2", LumberType.LUMBER_2X4, 800.0)

    graph.add_lumber_piece(lumber1)
    graph.add_lumber_piece(lumber2)

    joint = AlignedScrewJoint(
        src_face=Face.TOP,
        dst_face=Face.TOP,
        src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
        dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
    )

    graph.add_joint("comp1_beam1", "comp1_beam2", joint)

    # Component 2: Two connected pieces
    lumber3 = LumberPiece("comp2_beam1", LumberType.LUMBER_2X4, 1200.0)
    lumber4 = LumberPiece("comp2_beam2", LumberType.LUMBER_2X4, 1200.0)

    graph.add_lumber_piece(lumber3)
    graph.add_lumber_piece(lumber4)

    graph.add_joint("comp2_beam1", "comp2_beam2", joint)

    # Isolated piece
    lumber5 = LumberPiece("isolated", LumberType.LUMBER_2X4, 600.0)
    graph.add_lumber_piece(lumber5)

    return graph


@pytest.fixture
def complex_assembly():
    """Provide a complex furniture-like assembly."""
    graph = WoodworkingGraph()

    # Table-like structure with legs, frame, and top
    # Legs
    legs = [
        LumberPiece("leg_fl", LumberType.LUMBER_2X4, 750.0),  # front-left
        LumberPiece("leg_fr", LumberType.LUMBER_2X4, 750.0),  # front-right
        LumberPiece("leg_bl", LumberType.LUMBER_2X4, 750.0),  # back-left
        LumberPiece("leg_br", LumberType.LUMBER_2X4, 750.0),  # back-right
    ]

    # Frame pieces
    frame = [
        LumberPiece("frame_front", LumberType.LUMBER_2X4, 1200.0),
        LumberPiece("frame_back", LumberType.LUMBER_2X4, 1200.0),
        LumberPiece("frame_left", LumberType.LUMBER_2X4, 800.0),
        LumberPiece("frame_right", LumberType.LUMBER_2X4, 800.0),
    ]

    # Top supports
    supports = [
        LumberPiece("support1", LumberType.LUMBER_2X4, 1200.0),
        LumberPiece("support2", LumberType.LUMBER_2X4, 1200.0),
    ]

    # Add all pieces
    for piece in legs + frame + supports:
        graph.add_lumber_piece(piece)

    # Joint for vertical connections
    vert_joint = AlignedScrewJoint(
        src_face=Face.TOP,
        dst_face=Face.BOTTOM,
        src_edge_point=EdgePoint(Face.TOP, Face.FRONT, 0.5),
        dst_edge_point=EdgePoint(Face.BOTTOM, Face.FRONT, 0.5),
    )

    # Joint for horizontal connections
    horiz_joint = AlignedScrewJoint(
        src_face=Face.FRONT,
        dst_face=Face.BACK,
        src_edge_point=EdgePoint(Face.FRONT, Face.TOP, 0.5),
        dst_edge_point=EdgePoint(Face.BACK, Face.TOP, 0.5),
    )

    # Connect legs to frame
    graph.add_joint("leg_fl", "frame_front", vert_joint, assembly_order=1)
    graph.add_joint("leg_fr", "frame_front", vert_joint, assembly_order=2)
    graph.add_joint("leg_bl", "frame_back", vert_joint, assembly_order=3)
    graph.add_joint("leg_br", "frame_back", vert_joint, assembly_order=4)

    graph.add_joint("leg_fl", "frame_left", vert_joint, assembly_order=5)
    graph.add_joint("leg_bl", "frame_left", vert_joint, assembly_order=6)
    graph.add_joint("leg_fr", "frame_right", vert_joint, assembly_order=7)
    graph.add_joint("leg_br", "frame_right", vert_joint, assembly_order=8)

    # Connect frame pieces
    graph.add_joint("frame_front", "frame_left", horiz_joint, assembly_order=9)
    graph.add_joint("frame_front", "frame_right", horiz_joint, assembly_order=10)
    graph.add_joint("frame_back", "frame_left", horiz_joint, assembly_order=11)
    graph.add_joint("frame_back", "frame_right", horiz_joint, assembly_order=12)

    # Add supports
    graph.add_joint("frame_left", "support1", horiz_joint, assembly_order=13)
    graph.add_joint("frame_right", "support1", horiz_joint, assembly_order=14)
    graph.add_joint("frame_left", "support2", horiz_joint, assembly_order=15)
    graph.add_joint("frame_right", "support2", horiz_joint, assembly_order=16)

    return graph


@pytest.fixture
def large_grid_graph():
    """Provide a large grid-structured graph for performance testing."""
    graph = WoodworkingGraph()

    grid_size = 10

    # Create grid of pieces
    for i in range(grid_size):
        for j in range(grid_size):
            piece_id = f"beam_{i}_{j}"
            piece = LumberPiece(piece_id, LumberType.LUMBER_2X4, 1000.0)
            graph.add_lumber_piece(piece)

    # Connect in grid pattern
    joint = AlignedScrewJoint(
        src_face=Face.TOP,
        dst_face=Face.TOP,
        src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
        dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
    )

    order = 1
    for i in range(grid_size):
        for j in range(grid_size):
            current = f"beam_{i}_{j}"

            # Connect to right neighbor
            if j < grid_size - 1:
                right = f"beam_{i}_{j+1}"
                graph.add_joint(current, right, joint, assembly_order=order)
                order += 1

            # Connect to bottom neighbor
            if i < grid_size - 1:
                bottom = f"beam_{i+1}_{j}"
                graph.add_joint(current, bottom, joint, assembly_order=order)
                order += 1

    return graph


@pytest.fixture
def joints_collection():
    """Provide a collection of different joint types."""
    return {
        "top_to_top": AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.TOP,
            src_edge_point=EdgePoint(Face.TOP, Face.RIGHT, 0.5),
            dst_edge_point=EdgePoint(Face.TOP, Face.LEFT, 0.5),
        ),
        "top_to_bottom": AlignedScrewJoint(
            src_face=Face.TOP,
            dst_face=Face.BOTTOM,
            src_edge_point=EdgePoint(Face.TOP, Face.FRONT, 0.5),
            dst_edge_point=EdgePoint(Face.BOTTOM, Face.FRONT, 0.5),
        ),
        "front_to_back": AlignedScrewJoint(
            src_face=Face.FRONT,
            dst_face=Face.BACK,
            src_edge_point=EdgePoint(Face.FRONT, Face.TOP, 0.5),
            dst_edge_point=EdgePoint(Face.BACK, Face.TOP, 0.5),
        ),
        "left_to_right": AlignedScrewJoint(
            src_face=Face.LEFT,
            dst_face=Face.RIGHT,
            src_edge_point=EdgePoint(Face.LEFT, Face.TOP, 0.5),
            dst_edge_point=EdgePoint(Face.RIGHT, Face.TOP, 0.5),
        ),
    }


@pytest.fixture
def lumber_types_collection():
    """Provide a collection of different lumber pieces."""
    return {
        "2x4_short": LumberPiece("2x4_short", LumberType.LUMBER_2X4, 500.0),
        "2x4_medium": LumberPiece("2x4_medium", LumberType.LUMBER_2X4, 1000.0),
        "2x4_long": LumberPiece("2x4_long", LumberType.LUMBER_2X4, 2000.0),
        "2x8_medium": LumberPiece("2x8_medium", LumberType.LUMBER_2X8, 1000.0),
        "1x4_medium": LumberPiece("1x4_medium", LumberType.LUMBER_1X4, 1000.0),
    }
