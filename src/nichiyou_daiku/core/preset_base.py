"""Base classes for preset enumerations.

This module provides mixin classes for creating enums with string value lookup.
"""

from typing import Self


class StringEnumMixin:
    """Mixin for Enum with string value lookup.

    This mixin provides a common `.of()` classmethod for looking up enum members
    by their string value. It eliminates code duplication across multiple
    enum classes (Dowel, SlimScrew, CoarseThreadScrew, etc.).

    Example:
        >>> from enum import Enum
        >>> class Size(StringEnumMixin, Enum):
        ...     SMALL = "S"
        ...     MEDIUM = "M"
        ...     LARGE = "L"
        >>> Size.of("M")
        <Size.MEDIUM: 'M'>
        >>> Size.of("XL")
        Traceback (most recent call last):
            ...
        ValueError: Unknown Size: XL
    """

    @classmethod
    def of(cls, value: str) -> Self:
        """Look up an enum member by its string value.

        Args:
            value: The string value to look up

        Returns:
            The matching enum member

        Raises:
            ValueError: If no member matches the given value
        """
        for member in cls:  # type: ignore[var-annotated]
            if member.value == value:
                return member  # type: ignore[return-value]
        raise ValueError(f"Unknown {cls.__name__}: {value}")
