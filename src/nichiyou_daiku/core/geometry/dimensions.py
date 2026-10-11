"""Basic dimension types for woodworking.

This module provides basic dimension types used throughout the nichiyou-daiku
library. All dimensions are in millimeters for precision.
"""

from typing import Annotated

from pydantic import BaseModel, Field

# Use Annotated for both type checking and validation
# A non-negative float of millimeters, for dimensions where negative values
# make no sense. The constraint is enforced when used as a pydantic field.
Millimeters = Annotated[float, Field(ge=0)]


class Shape2D(BaseModel, frozen=True):
    """2D shape with width and height in millimeters.

    Represents the cross-section of a piece of lumber.

    Attributes:
        width: Width in millimeters (must be non-negative)
        height: Height in millimeters (must be non-negative)

    Examples:
        >>> shape = Shape2D(width=89.0, height=38.0)  # 2x4 actual dimensions
        >>> shape.width
        89.0
        >>> shape.height
        38.0
        >>> # Immutable - cannot modify after creation
        >>> from pydantic import ValidationError
        >>> import pytest
        >>> with pytest.raises(ValidationError):
        ...     shape.width = 50.0
    """

    width: Millimeters
    height: Millimeters


class Shape3D(BaseModel, frozen=True):
    """3D shape with width, height, and length in millimeters.

    Represents a complete piece of lumber with all three dimensions.

    Attributes:
        width: Width in millimeters (must be non-negative)
        height: Height in millimeters (must be non-negative)
        length: Length in millimeters (must be non-negative)

    Examples:
        >>> shape = Shape3D(width=89.0, height=38.0, length=1000.0)
        >>> shape.length
        1000.0
        >>> # Zero dimensions are now allowed
        >>> shape_with_zero = Shape3D(width=0.0, height=89.0, length=1000.0)
        >>> shape_with_zero.width
        0.0
        >>> # Negative dimensions are not allowed
        >>> from pydantic import ValidationError
        >>> import pytest
        >>> with pytest.raises(ValidationError):
        ...     Shape3D(width=89.0, height=38.0, length=-100)
    """

    width: Millimeters
    height: Millimeters
    length: Millimeters
