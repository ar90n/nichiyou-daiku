"""Lumber piece definitions and utilities.

This module defines the core types for representing lumber pieces in the
nichiyou-daiku woodworking system.
"""

from enum import Enum
from typing import Type, overload
from uuid import uuid4

from pydantic import BaseModel

from nichiyou_daiku.core.geometry import Millimeters, Shape2D, Shape3D


class PieceType(Enum):
    """Enumeration of supported lumber piece types.

    Examples:
        >>> PieceType.PT_2x4
        <PieceType.PT_2x4: '2x4'>
        >>> PieceType.PT_2x4.value
        '2x4'
    """

    PT_2x4 = "2x4"
    PT_1x4 = "1x4"

    @classmethod
    def of(cls, value: str) -> "PieceType":
        """Create a PieceType instance from a string value.

        Args:
            value: String representation of piece type (e.g., "2x4")

        Returns:
            PieceType enum instance

        Raises:
            ValueError: If the piece type is not supported

        Examples:
            >>> PieceType.of("2x4")
            <PieceType.PT_2x4: '2x4'>
            >>> PieceType.of("2x4") == PieceType.PT_2x4
            True
            >>> import pytest
            >>> with pytest.raises(ValueError) as exc:
            ...     PieceType.of("2x6")
            >>> "Unsupported piece type: 2x6" in str(exc.value)
            True
        """
        ret = {
            "1x4": cls.PT_1x4,
            "2x4": cls.PT_2x4,
        }.get(value)
        if ret is not None:
            return ret

        raise ValueError(f"Unsupported piece type: {value}")


class Piece(BaseModel, frozen=True):
    """A piece of lumber with specific dimensions.

    Attributes:
        id: Unique identifier for the piece
        type: Type of lumber (e.g., 2x4)
        length: Length in millimeters

    Examples:
        >>> piece = Piece(id="test-1", type=PieceType.PT_2x4, length=1000.0)
        >>> piece.id
        'test-1'
        >>> piece.type
        <PieceType.PT_2x4: '2x4'>
        >>> piece.length
        1000.0
    """

    id: str
    type: PieceType
    length: Millimeters

    @classmethod
    def of(
        cls: Type["Piece"],
        piece_type: PieceType,
        length: Millimeters,
        id_: str | None = None,
    ) -> "Piece":
        """Create a Piece instance from type and length.

        Args:
            piece_type: Type of lumber
            length: Length in millimeters
            id_: Optional ID, generates UUID if not provided

        Returns:
            New Piece instance

        Examples:
            >>> piece = Piece.of(PieceType.PT_2x4, 1500.0, "custom-id")
            >>> piece.id
            'custom-id'
            >>> piece.length
            1500.0
            >>> # Auto-generated ID
            >>> piece2 = Piece.of(PieceType.PT_2x4, 2000.0)
            >>> len(piece2.id) == 36  # UUID length
            True
        """
        if id_ is None:
            id_ = str(uuid4())
        return cls(id=id_, type=piece_type, length=length)


@overload
def get_shape(value: PieceType) -> Shape2D: ...
@overload
def get_shape(value: Piece) -> Shape3D: ...
def get_shape(value: PieceType | Piece):
    """Get the shape of the piece based on its type or Piece instance.

    This is an overloaded function that returns:
    - Shape2D when given a PieceType (cross-section)
    - Shape3D when given a Piece (includes length)

    Args:
        value: Either a PieceType or Piece instance

    Returns:
        Shape2D or Shape3D depending on input type

    Examples:
        >>> # Get 2D shape from PieceType
        >>> shape2d = get_shape(PieceType.PT_2x4)
        >>> shape2d.height
        38.0
        >>> shape2d.width
        89.0
        >>> # Get 3D shape from Piece
        >>> piece = Piece.of(PieceType.PT_2x4, 1000.0)
        >>> shape3d = get_shape(piece)
        >>> shape3d.width
        89.0
        >>> shape3d.length
        1000.0
    """
    match value:
        case PieceType():
            return _get_shape_of_piece_type(value)
        case Piece():
            return _get_shape_of_piece(value)


def _get_shape_of_piece_type(piece_type: PieceType) -> Shape2D:
    """Get the 2D cross-section shape of a piece type.

    Internal function that maps piece types to their actual dimensions.

    Args:
        piece_type: Type of lumber

    Returns:
        2D shape with actual dimensions in millimeters

    Examples:
        >>> shape = _get_shape_of_piece_type(PieceType.PT_2x4)
        >>> shape.width  # Actual 2x4 width
        89.0
        >>> shape.height  # Actual 2x4 height
        38.0
    """
    match piece_type:
        case PieceType.PT_2x4:
            return Shape2D(width=89.0, height=38.0)  # 2x4 actual dimensions in mm
        case PieceType.PT_1x4:
            return Shape2D(width=89.0, height=19.0)  #

    raise RuntimeError(
        f"Unsupported piece type: {piece_type}. "
        "Please implement the cross-section dimensions."
    )


def _get_shape_of_piece(piece: Piece) -> Shape3D:
    """Get the 3D shape of the piece based on its type and length.

    Internal function that combines cross-section with length.

    Args:
        piece: Piece instance with type and length

    Returns:
        3D shape with all dimensions

    Examples:
        >>> piece = Piece.of(PieceType.PT_2x4, 1500.0)
        >>> shape = _get_shape_of_piece(piece)
        >>> shape.width
        89.0
        >>> shape.height
        38.0
        >>> shape.length
        1500.0
    """
    shape_2d = get_shape(piece.type)
    return Shape3D(width=shape_2d.width, height=shape_2d.height, length=piece.length)
