"""Dowel specifications for wood connections.

This module defines standard dowel sizes commonly used in DIY woodworking.
"""

from enum import Enum
from typing import TypeAlias

from pydantic import BaseModel

from nichiyou_daiku.core.geometry import Millimeters


class DowelSpec(BaseModel, frozen=True):
    """Specification for a dowel (diameter and length).

    Attributes:
        diameter: Dowel diameter in mm
        length: Dowel length in mm

    Example:
        >>> spec = DowelSpec(diameter=8.0, length=30.0)
        >>> spec.diameter
        8.0
        >>> spec.length
        30.0
    """

    diameter: Millimeters
    length: Millimeters


class Dowel(Enum):
    """Standard wooden dowel sizes.

    Common dowel sizes available in Japan, based on standard product offerings.

    Naming convention: D{diameter}_L{length}
    - Diameter in mm
    - Length in mm

    Example:
        >>> Dowel.D8_L30.value
        '8x30'
        >>> Dowel.of("8x30")
        <Dowel.D8_L30: '8x30'>
    """

    # 6mm diameter
    D6_L25 = "6x25"
    D6_L30 = "6x30"

    # 8mm diameter
    D8_L25 = "8x25"
    D8_L30 = "8x30"
    D8_L40 = "8x40"

    # 10mm diameter
    D10_L30 = "10x30"
    D10_L40 = "10x40"

    # 12mm diameter
    D12_L40 = "12x40"

    @classmethod
    def of(cls, value: str) -> "Dowel":
        """Create a Dowel from a string value.

        Args:
            value: String in format "diameter x length" (e.g., "8x30")

        Returns:
            Dowel enum member

        Raises:
            ValueError: If the value doesn't match any known size
        """
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"Unknown dowel size: {value}")


# Type alias for future expansion (e.g., different wood types)
DowelPreset: TypeAlias = Dowel


def as_spec(dowel: DowelPreset) -> DowelSpec:
    """Get DowelSpec from a preset dowel type.

    Args:
        dowel: A Dowel enum member

    Returns:
        DowelSpec with the corresponding diameter and length

    Example:
        >>> spec = as_spec(Dowel.D8_L30)
        >>> spec.diameter
        8.0
        >>> spec.length
        30.0
    """
    diameter_str, length_str = dowel.value.split("x")
    return DowelSpec(diameter=float(diameter_str), length=float(length_str))


def find_preset(diameter: float, length: float) -> DowelPreset | None:
    """Find a dowel preset by dimensions.

    This function is primarily used by the DSL parser to validate and lookup
    dowel presets from their string representation.

    Args:
        diameter: Dowel diameter in mm
        length: Dowel length in mm

    Returns:
        The matching DowelPreset (Dowel) if found,
        None if no matching preset exists.

    Example:
        >>> find_preset(8, 30)
        <Dowel.D8_L30: '8x30'>
        >>> find_preset(9, 99) is None
        True
    """
    value = f"{int(diameter)}x{int(length)}"
    try:
        return Dowel.of(value)
    except ValueError:
        return None
