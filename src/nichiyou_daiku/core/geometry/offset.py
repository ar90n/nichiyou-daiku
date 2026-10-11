from typing import Literal

from pydantic import BaseModel, Field

from .dimensions import Millimeters


class FromMax(BaseModel, frozen=True):
    """Offset measured from the maximum edge of a dimension.

    Examples:
        >>> offset = FromMax(value=100.0)
        >>> offset.value
        100.0
        >>> # Zero is allowed
        >>> zero_offset = FromMax(value=0.0)
        >>> zero_offset.value
        0.0
        >>> # Negative values are not allowed
        >>> from pydantic import ValidationError
        >>> import pytest
        >>> with pytest.raises(ValidationError):
        ...     FromMax(value=-10)
    """

    value: Millimeters
    # Both offsets share the {value} schema; the tag keeps JSON round trips
    # from turning a FromMin into a FromMax.
    kind: Literal["from_max"] = Field(default="from_max", repr=False)


class FromMin(BaseModel, frozen=True):
    """Offset measured from the minimum edge of a dimension.

    Examples:
        >>> offset = FromMin(value=150.0)
        >>> offset.value
        150.0
        >>> # Different type from FromMax
        >>> max_offset = FromMax(value=100.0)
        >>> min_offset = FromMin(value=100.0)
        >>> type(max_offset) != type(min_offset)
        True
    """

    value: Millimeters
    kind: Literal["from_min"] = Field(default="from_min", repr=False)


Offset = FromMax | FromMin


def evaluate(length: Millimeters, offset: Offset) -> Millimeters:
    match offset:
        case FromMax(value=v):
            return length - v
        case FromMin(value=v):
            return v
