"""General joint connector for connecting lumber pieces.

This module implements the general joint system where lumber pieces
are connected based on face locations and orientations.
"""

from dataclasses import dataclass
from nichiyou_daiku.core.lumber import Face


@dataclass(frozen=True)
class JointLocation:
    """Location on a face for joint connection.
    
    Attributes:
        face: The face where the joint is located
        offset: Offset from face center along the U-axis in mm
    """
    face: Face
    offset: float


@dataclass(frozen=True)
class JointPose:
    """Orientation of the target piece in a joint.
    
    Attributes:
        aligned: Face whose normal aligns with the base face's joint coordinate system's positive direction
        aux_aligned: Face used to resolve ambiguity when target face is contained within base face
    """
    aligned: Face
    aux_aligned: Face


@dataclass(frozen=True)
class GeneralJoint:
    """General joint connecting two lumber pieces.
    
    This joint type defines connection between a base face and a target face,
    with the target's orientation specified by JointPose.
    
    Attributes:
        base_loc: Location on the base piece where joint connects
        target_loc: Location on the target piece where joint connects
        target_pose: Orientation of the target piece
    """
    base_loc: JointLocation
    target_loc: JointLocation
    target_pose: JointPose
