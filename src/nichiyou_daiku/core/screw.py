"""Screw specifications for wood connections.

This module defines standard screw sizes commonly used in DIY woodworking,
including slim screws (スリムビス) and coarse thread screws (コーススレッド).
"""

from enum import Enum
from typing import TypeAlias

from pydantic import BaseModel

from nichiyou_daiku.core.geometry import Millimeters


class ScrewSpec(BaseModel, frozen=True):
    """Specification for a screw (diameter and length).

    Attributes:
        diameter: Screw diameter in mm
        length: Screw length in mm

    Example:
        >>> spec = ScrewSpec(diameter=3.8, length=50.0)
        >>> spec.diameter
        3.8
        >>> spec.length
        50.0
    """

    diameter: Millimeters
    length: Millimeters


class SlimScrew(Enum):
    """Standard slim screw (スリムビス) sizes.

    Slim screws are thinner than coarse thread screws and are less likely
    to split wood. They typically don't require pilot holes.

    Naming convention: D{diameter}_L{length}
    - Diameter in mm (with underscore replacing decimal point)
    - Length in mm

    Example:
        >>> SlimScrew.D3_3_L50.value
        '3.3x50'
        >>> SlimScrew.of("3.3x50")
        <SlimScrew.D3_3_L50: '3.3x50'>
    """

    # 3.3mm diameter
    D3_3_L25 = "3.3x25"
    D3_3_L30 = "3.3x30"
    D3_3_L35 = "3.3x35"
    D3_3_L40 = "3.3x40"
    D3_3_L45 = "3.3x45"
    D3_3_L50 = "3.3x50"

    # 3.8mm diameter
    D3_8_L55 = "3.8x55"
    D3_8_L60 = "3.8x60"
    D3_8_L65 = "3.8x65"
    D3_8_L70 = "3.8x70"
    D3_8_L75 = "3.8x75"

    # 4.2mm diameter
    D4_2_L90 = "4.2x90"

    @classmethod
    def of(cls, value: str) -> "SlimScrew":
        """Create a SlimScrew from a string value.

        Args:
            value: String in format "diameter x length" (e.g., "3.3x50")

        Returns:
            SlimScrew enum member

        Raises:
            ValueError: If the value doesn't match any known size
        """
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"Unknown slim screw size: {value}")


class CoarseThreadScrew(Enum):
    """Standard coarse thread screw (コーススレッド) sizes.

    Coarse thread screws have larger pitch and stronger holding power.
    They are the standard choice for heavy-duty applications.

    Naming convention: D{diameter}_L{length}
    - Diameter in mm (with underscore replacing decimal point)
    - Length in mm

    Example:
        >>> CoarseThreadScrew.D3_8_L57.value
        '3.8x57'
        >>> CoarseThreadScrew.of("3.8x57")
        <CoarseThreadScrew.D3_8_L57: '3.8x57'>
    """

    # 3.8mm diameter
    D3_8_L25 = "3.8x25"
    D3_8_L30 = "3.8x30"
    D3_8_L35 = "3.8x35"
    D3_8_L40 = "3.8x40"
    D3_8_L45 = "3.8x45"
    D3_8_L50 = "3.8x50"
    D3_8_L57 = "3.8x57"

    # 4.2mm diameter
    D4_2_L65 = "4.2x65"
    D4_2_L75 = "4.2x75"

    # 4.5mm diameter
    D4_5_L90 = "4.5x90"
    D4_5_L100 = "4.5x100"

    # 5.2mm diameter
    D5_2_L120 = "5.2x120"

    @classmethod
    def of(cls, value: str) -> "CoarseThreadScrew":
        """Create a CoarseThreadScrew from a string value.

        Args:
            value: String in format "diameter x length" (e.g., "3.8x57")

        Returns:
            CoarseThreadScrew enum member

        Raises:
            ValueError: If the value doesn't match any known size
        """
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"Unknown coarse thread screw size: {value}")


# Type alias for any preset screw type
ScrewPreset: TypeAlias = SlimScrew | CoarseThreadScrew


def as_spec(screw: ScrewPreset) -> ScrewSpec:
    """Get ScrewSpec from a preset screw type.

    Args:
        screw: A SlimScrew or CoarseThreadScrew enum member

    Returns:
        ScrewSpec with the corresponding diameter and length

    Example:
        >>> spec = get_spec(SlimScrew.D3_3_L50)
        >>> spec.diameter
        3.3
        >>> spec.length
        50.0
        >>> spec = get_spec(CoarseThreadScrew.D3_8_L57)
        >>> spec.diameter
        3.8
        >>> spec.length
        57.0
    """
    # Parse "diameter x length" format
    diameter_str, length_str = screw.value.split("x")
    return ScrewSpec(diameter=float(diameter_str), length=float(length_str))


def find_preset(screw_type: str, diameter: float, length: float) -> ScrewPreset | None:
    """Find a screw preset by type name and dimensions.

    This function is primarily used by the DSL parser to validate and lookup
    screw presets from their string representation.

    Args:
        screw_type: Either "Slim" or "Coarse"
        diameter: Screw diameter in mm
        length: Screw length in mm

    Returns:
        The matching ScrewPreset (SlimScrew or CoarseThreadScrew) if found,
        None if no matching preset exists.

    Example:
        >>> find_preset("Slim", 3.3, 50)
        <SlimScrew.D3_3_L50: '3.3x50'>
        >>> find_preset("Coarse", 3.8, 57)
        <CoarseThreadScrew.D3_8_L57: '3.8x57'>
        >>> find_preset("Slim", 9.9, 999) is None
        True
    """
    value = f"{diameter}x{int(length)}"
    if screw_type == "Slim":
        try:
            return SlimScrew.of(value)
        except ValueError:
            return None
    elif screw_type == "Coarse":
        try:
            return CoarseThreadScrew.of(value)
        except ValueError:
            return None
    return None
