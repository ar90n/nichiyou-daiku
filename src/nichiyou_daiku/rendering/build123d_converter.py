"""Convert woodworking graph to build123d objects."""

from typing import Optional, Tuple, Dict
import logging

from build123d import Box, Compound, Location, Solid, RigidJoint, Axis, Face, Vector, Rotation

from nichiyou_daiku.graph.woodworking_graph import WoodworkingGraph
from nichiyou_daiku.core.lumber import LumberPiece, LumberFace, get_shape, calc_angle, LumberAxis, LumberDirection, LumberPolarity
from nichiyou_daiku.connectors.general import TargetAnchor, TargetAnchorCenter, TargetAnchorMax, TargetAnchorMin, TargetPose, TargetPosition, BasePosition, BaseOffset, BaseOffsetValue, BaseOffsetMin, BaseOffsetMax

logger = logging.getLogger(__name__)


def box_from(
    piece: LumberPiece,
) -> Solid:
    shape = get_shape(piece)
    return Box(length=shape.length, width=shape.width, height=shape.height)

def unit_direction_from(
    face: LumberFace,
) -> Vector:
    """Get the unit direction vector for a lumber face."""
    return {
        LumberFace.TOP: Axis.Y.direction,      # U-axis: RIGHT -> LEFT (negative X)
        LumberFace.BOTTOM: Axis.Y.direction,   # U-axis: RIGHT -> LEFT (negative X)
        LumberFace.LEFT: Axis.X.direction,      # U-axis: BOTTOM -> TOP (positive Z)
        LumberFace.RIGHT: Axis.X.direction,     # U-axis: BOTTOM -> TOP (positive Z)
        LumberFace.FRONT: Axis.X.direction,     # U-axis: BOTTOM -> TOP (positive Z)
        LumberFace.BACK: Axis.X.direction       # U-axis: BOTTOM -> TOP (positive Z)
    }[face]

def face_from(
    box: Box,
    face: LumberFace
) -> Face:
    """Get the build123d face corresponding to a lumber face."""
    # Map lumber faces to build123d box faces based on new definitions
    # TOP/BOTTOM are along Z axis (length)
    # FRONT/BACK are along Y axis (height) 
    # LEFT/RIGHT are along X axis (width)
    axis = {
        LumberFace.TOP: Axis.X,      # Along length axis
        LumberFace.BOTTOM: Axis.X,   # Along length axis
        LumberFace.LEFT: Axis.Y,     # Along width axis
        LumberFace.RIGHT: Axis.Y,    # Along width axis
        LumberFace.FRONT: Axis.Z,    # Along height axis
        LumberFace.BACK: Axis.Z      # Along height axis
    }[face]

    order = {
        LumberFace.TOP: -1,      # Max Z
        LumberFace.BOTTOM: 0,    # Min Z
        LumberFace.LEFT: 0,      # Min X
        LumberFace.RIGHT: -1,    # Max X
        LumberFace.FRONT: -1,    # Max Y
        LumberFace.BACK: 0       # Min Y
    }[face]

    return box.faces().sort_by(axis)[order]


#def get_aligned_axis(
#    base_face: LumberFace,
#    target_face: LumberFace
#) -> Axis:
#    """Get the aligned axis based on base and target faces."""
#    # Map lumber faces to build123d axes
#    axis_map = {
#        LumberFace.TOP: Axis.X,
#        LumberFace.BOTTOM: Axis.X,
#        LumberFace.LEFT: Axis.Y,
#        LumberFace.RIGHT: Axis.Y,
#        LumberFace.FRONT: Axis.Z,
#        LumberFace.BACK: Axis.Z
#    }
#
#    base_axis = axis_map[base_face]
#    target_axis = axis_map[target_face]
#
#    if base_axis == target_axis:
#        return base_axis
#
#    # If they are not aligned, return None or raise an error
#    raise ValueError(f"Base face {base_face} and target face {target_face} are not aligned.")
#
#
#
#def base_location_from(
#    base_fase: Face,
#    target_face: Face,
#    base_pos: BasePosition,
#    target_pos: TargetPosition
#) -> Location:
#    """Get the build123d location for a base position."""
#    face = face_from(base_box, base_position.face)
#    location = face.center_location
#
#    def calc_target_offset(box: Box, target_anchor: TargetAnchor) -> float:
#        case target_anchor:
#            TargetAnchorCenter:
#                return 0.0
#            TargetAnchorMax:
#                return box.dimensions[face.axis].max
#            TargetAnchorMin:
#                return box.dimensions[face.axis].min
#
#    def calc_base_offset(box: Box, base_offset: BaseOffset, target_anchor: TargetAnchor) -> float:
#        case base_offset:
#            BaseOffsetValue:
#                return base_offset.value
#            BaseOffsetMin:
#                return box.dimensions[face.axis].min
#            BaseOffsetMax:
#                return box.dimensions[face.axis].max
#
#    #if isinstance(base_position.offset, BaseOffsetValue):
#    #    location.position += unit_direction_from(base_position.face) * base_position.offset.value
#    #elif isinstance(base_position.offset, BaseOffsetMin):
#    #    location.position += unit_direction_from(base_position.face) * box.dimensions[face.axis].min
#    #elif isinstance(base_position.offset, BaseOffsetMax):
#    #    location.position += unit_direction_from(base_position.face) * box.dimensions[face.axis].max
#    return location
#
#def location_from_target(
#    box: Box,
#    target_position: TargetPosition
#) -> Location:
#    """Get the build123d location for a target position."""
#    face = face_from(box, target_position.face)
#    location = face.center_location
#
#    if isinstance(target_position.anchor, TargetAnchorCenter):
#        # Center of the face
#        pass
#    elif isinstance(target_position.anchor, TargetAnchorMax):
#        # Max along the face normal
#        location.position += unit_direction_from(target_position.face) * box.dimensions[face.axis].max
#    elif isinstance(target_position.anchor, TargetAnchorMin):
#        # Min along the face normal
#        location.position += unit_direction_from(target_position.face) * box.dimensions[face.axis].min
#
#    return location

def location_from(
    box: Box,
    joint_position:  BasePosition | TargetPosition
) -> Location:
    return face_from(box, joint_position.face).center_location


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
    boxes = {
        _id: box_from(piece) for _id, piece in graph.lumbers()
    }

    for base_id, target_id, joint in graph.joints():
        base_box = boxes[base_id]
        target_box = boxes[target_id]

        base_joint = RigidJoint(
            label=f"{base_id}-{target_id}",
            to_part=base_box,
            joint_location= location_from(
                base_box,
                joint.base_pos
            )
        )

        default_orth_face = {
            LumberFace.TOP: LumberFace.BOTTOM,
            LumberFace.BOTTOM: LumberFace.TOP,
            LumberFace.LEFT: LumberFace.RIGHT,
            LumberFace.RIGHT: LumberFace.LEFT,
            LumberFace.FRONT: LumberFace.BACK,
            LumberFace.BACK: LumberFace.FRONT
        }

# lenght ->  widht -> height -> length
        unit_angle = {
            LumberFace.TOP: Vector(1, 0, 0),
            LumberFace.BOTTOM: Vector(-1, 0, 0),
            LumberFace.LEFT: Vector(0, 0, 1),
            LumberFace.RIGHT: Vector(0, 0, -1),
            LumberFace.FRONT: Vector(0, 0, 1),
            LumberFace.BACK: Vector(0, 0, -1),
        }[joint.target_pos.face]
        up_face = {
            LumberFace.TOP: LumberFace.FRONT,
            LumberFace.BOTTOM: LumberFace.FRONT,
            LumberFace.LEFT: LumberFace.FRONT,
            LumberFace.RIGHT: LumberFace.FRONT,
            LumberFace.FRONT: LumberFace.TOP,
            LumberFace.BACK: LumberFace.TOP
        }[joint.target_pos.face]
        rot_axis = {
            LumberFace.TOP: LumberDirection(LumberAxis.LENGTH, LumberPolarity.FORWARD),
            LumberFace.BOTTOM: LumberDirection(LumberAxis.LENGTH, LumberPolarity.BACKWARD),
            LumberFace.LEFT: LumberDirection(LumberAxis.WIDTH, LumberPolarity.BACKWARD),
            LumberFace.RIGHT: LumberDirection(LumberAxis.WIDTH, LumberPolarity.FORWARD),
            LumberFace.FRONT: LumberDirection(LumberAxis.HEIGHT, LumberPolarity.FORWARD),
            LumberFace.BACK: LumberDirection(LumberAxis.HEIGHT, LumberPolarity.BACKWARD)
        }[joint.target_pos.face]

        print(joint)
        rot_angle = calc_angle(rot_axis, up_face, joint.target_pose.aligned)
        print(rot_angle, unit_angle, rot_angle * unit_angle)

        jl=-location_from(
            target_box,
            joint.target_pos
        )
        print(jl.orientation)
        jl.orientation += rot_angle * unit_angle
        print(jl.orientation)
        #jl.orientation = Vector(0, -90, 0)
        #print(dir(jl), dir(jl.to_axis().direction.rotate()))
        target_joint = RigidJoint(
            label=f"{target_id}-{base_id}",
            to_part=target_box,
            joint_location=jl
        )
        base_joint.connect_to(target_joint)

    return Compound(children=boxes.values())