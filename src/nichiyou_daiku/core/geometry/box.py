"""3D bounding box type.

This module provides the Box type for representing 3D bounding boxes.
"""

from pydantic import BaseModel

from .dimensions import Shape3D


class Box(BaseModel, frozen=True):
    """3D bounding box.

    Attributes:
        shape: 3D shape defining the box dimensions

    Examples:
        >>> from nichiyou_daiku.core.geometry.dimensions import Shape3D
        >>> box = Box(shape=Shape3D(width=89.0, height=38.0, length=1000.0))
        >>> box.shape.width
        89.0
        >>> box.shape.height
        38.0
        >>> box.shape.length
        1000.0
    """

    shape: Shape3D
