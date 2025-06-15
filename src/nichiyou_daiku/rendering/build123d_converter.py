"""Convert woodworking graph to build123d objects."""

from typing import Optional, Tuple, Dict
import logging

from build123d import Box, Compound, Location, Solid, RigidJoint, Axis, Face, Vector

from nichiyou_daiku.graph.woodworking_graph import WoodworkingGraph
from nichiyou_daiku.core.lumber import LumberPiece, Face as LumberFace

# Type aliases
Position3D = Tuple[float, float, float]
Rotation3D = Tuple[float, float, float]

logger = logging.getLogger(__name__)


def lumber_to_box(
    piece: LumberPiece,
) -> Solid:
    """Convert a lumber piece to a build123d Box.

    This is a standalone function for Task 4.2.

    Args:
        piece: The lumber piece to convert

    Returns:
        A build123d Box solid with correct dimensions and position
    """
    # Get dimensions from lumber type
    dimensions = piece.get_dimensions()
    width, height, length = dimensions

    # Create box at origin (note: build123d expects length, width, height order)
    box = Box(length, width, height)
    return box


def graph_to_assembly(
    graph: WoodworkingGraph,
) -> Optional[Compound]:
    """Convert a woodworking graph to a build123d assembly.

    This is a standalone function for Task 4.3.

    Args:
        graph: The woodworking graph to convert

    Returns:
        A build123d Compound containing all pieces,
        or None if graph is empty
    """
    # Collect all boxes
    boxes = {}
    for node_id in graph._graph.nodes():
        node_data = graph.get_lumber_data(node_id)
        piece = node_data.lumber_piece

        boxes[node_id] = lumber_to_box(piece)

    for edge in graph._graph.edges():
        base, target = edge
        src_box = boxes[base]
        dst_box = boxes[target]
        joint = graph.get_joint_data(base, target).joint

        def get_face(box: Box, face: LumberFace) -> Face:
            axis = {
                LumberFace.TOP: Axis.X,
                LumberFace.BOTTOM: Axis.X,
                LumberFace.LEFT: Axis.Z,
                LumberFace.RIGHT: Axis.Z,
                LumberFace.FRONT: Axis.Y,
                LumberFace.BACK: Axis.Y
            }[face]

            order = {
                LumberFace.TOP: -1,
                LumberFace.BOTTOM: 0,
                LumberFace.LEFT: 0,
                LumberFace.RIGHT: -1,
                LumberFace.FRONT: 0,
                LumberFace.BACK: -1
            }[face]

            return box.faces().sort_by(axis)[order]
        
        def get_unit(face: LumberFace) -> Vector:
            return {
                LumberFace.TOP: Axis.Z,
                LumberFace.BOTTOM: Axis.Z,
                LumberFace.LEFT: Axis.X,
                LumberFace.RIGHT: Axis.X,
                LumberFace.FRONT: Axis.X,
                LumberFace.BACK: Axis.X
            }[face].direction


        jl = -get_face(src_box, joint.base_loc.face).center_location
        jl.position += get_unit(joint.base_loc.face) * joint.base_loc.offset
        RigidJoint(
            label=f"{base}-{target}",
            to_part=src_box,
            joint_location=jl
        )

        jl2 = get_face(dst_box, joint.target_loc.face).center_location
        #print(get_face(dst_box, joint.target_pose.aligned).center_location.orientation., jl.orientation)
        RigidJoint(
            label=f"{target}-{base}",
            to_part=dst_box,
            joint_location=get_face(dst_box, joint.target_loc.face).center_location
        )
        src_box.joints[f"{base}-{target}"].connect_to(dst_box.joints[f"{target}-{base}"])

    return Compound(children=boxes.values())