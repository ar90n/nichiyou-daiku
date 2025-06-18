"""General joint connector for connecting lumber pieces.

This module implements the general joint system where lumber pieces
are connected based on face locations and orientations.
"""

from dataclasses import dataclass
from typing import TypeAlias

from nichiyou_daiku.core.lumber import LumberFace
from nichiyou_daiku.core.geometry import Millimeters

@dataclass(frozen=True)
class BaseOffsetValue:
    value: Millimeters

@dataclass(frozen=True)
class BaseOffsetMin:
    pass

@dataclass(frozen=True)
class BaseOffsetMax:
    pass

BaseOffset: TypeAlias = BaseOffsetValue | BaseOffsetMin | BaseOffsetMax

@dataclass(frozen=True)
class TargetAnchorMax:
    pass

@dataclass(frozen=True)
class TargetAnchorCenter:
    pass

@dataclass(frozen=True)
class TargetAnchorMin:
    pass

TargetAnchor: TypeAlias = TargetAnchorMax | TargetAnchorCenter | TargetAnchorMin

@dataclass(frozen=True)
class BasePosition:
    face: LumberFace
    offset: BaseOffset

@dataclass(frozen=True)
class TargetPosition:
    face: LumberFace
    anchor: TargetAnchor


@dataclass(frozen=True)
class TargetPose:
    aligned: LumberFace
    aux_aligned: LumberFace


@dataclass(frozen=True)
class GeneralJoint:
    base_pos: BasePosition
    target_pos: TargetPosition
    target_pose: TargetPose
