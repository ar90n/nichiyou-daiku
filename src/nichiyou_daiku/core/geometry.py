from typing import NewType
from dataclasses import dataclass

Millimeters = NewType("Millimeters", float)

@dataclass(frozen=True)
class Shape2D:
    width: Millimeters
    height: Millimeters

@dataclass(frozen=True)
class Shape3D:
    width: Millimeters
    height: Millimeters
    length: Millimeters