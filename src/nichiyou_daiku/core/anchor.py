"""Anchor types for specifying connection points on lumber pieces.

This module defines the Anchor class and related functions for
specifying where connections occur on pieces.
"""

from pydantic import BaseModel, model_validator

from nichiyou_daiku.core.geometry import (
    Box,
    Face,
    Edge,
    EdgePoint,
    SurfacePoint,
    Offset,
    Point3D,
    cross as cross_face,
    edge_length_of,
    is_positive,
    is_adjacent,
)
from nichiyou_daiku.core.piece import Piece, get_shape, shape_for_checks


OFFSET_TOLERANCE_MM = 1e-6
"""Slack for offsets computed in floating point, e.g. (400 / 11) * 11."""


def _get_pos_dir_edge(contact_face: Face, edge_shared_face: Face) -> Edge:
    if is_positive(cross_face(contact_face, edge_shared_face)):
        return Edge(lhs=contact_face, rhs=edge_shared_face)
    else:
        return Edge(lhs=edge_shared_face, rhs=contact_face)


class Anchor(BaseModel, frozen=True):
    """Specifies a connection point on a piece.

    An anchor defines where a connection occurs using:
    - contact_face: The face that makes contact with the other piece
    - edge_shared_face: The face that shares an edge with the contact face
    - offset: The position along the edge, or None when it is unknown: the
      two pieces may then slide along the edge (see ``resolve_model``)

    Examples:
        >>> from nichiyou_daiku.core.geometry import FromMin
        >>> anchor = Anchor(
        ...     contact_face="front",
        ...     edge_shared_face="top",
        ...     offset=FromMin(value=100)
        ... )
        >>> anchor.contact_face
        'front'
    """

    edge_shared_face: Face
    contact_face: Face
    offset: Offset | None

    @model_validator(mode="after")
    def _check_faces_adjacent(self) -> "Anchor":
        if not is_adjacent(self.contact_face, self.edge_shared_face):
            raise ValueError(
                f"contact_face '{self.contact_face}' and edge_shared_face "
                f"'{self.edge_shared_face}' must be adjacent faces"
            )
        return self

    @classmethod
    def of(
        cls, contact_face: Face, edge_shared_face: Face, offset: Offset | None
    ) -> "Anchor":
        """Create an Anchor instance.

        Args:
            contact_face: The face that makes contact with the other piece
            edge_shared_face: The face that shares an edge with the contact face
            offset: The position along the edge, or None if unknown

        Returns:
            Anchor instance

        Raises:
            ValueError: If contact_face and edge_shared_face are not adjacent
        """
        return cls(
            contact_face=contact_face,
            edge_shared_face=edge_shared_face,
            offset=offset,
        )


def as_edge_point(anchor: Anchor) -> EdgePoint:
    """Convert an anchor to an edge point.

    Args:
        anchor: The anchor to convert

    Returns:
        EdgePoint representing the anchor's position on the edge
    """
    if anchor.offset is None:
        raise ValueError("The anchor's offset is unknown; resolve the model first")
    return EdgePoint(
        edge=_get_pos_dir_edge(
            contact_face=anchor.contact_face,
            edge_shared_face=anchor.edge_shared_face,
        ),
        offset=anchor.offset,
    )


class BoundAnchor(BaseModel, frozen=True):
    """An anchor bound to a specific piece.

    Combines a piece with an anchor position, representing a concrete
    attachment point on a specific piece.

    Attributes:
        piece: The piece this anchor belongs to
        anchor: The anchor position specification
    """

    piece: Piece
    anchor: Anchor

    @model_validator(mode="after")
    def _check_offset_within_edge(self) -> "BoundAnchor":
        if self.anchor.offset is None:
            return self
        box = Box(shape=shape_for_checks(self.piece))
        edge = _get_pos_dir_edge(self.anchor.contact_face, self.anchor.edge_shared_face)
        max_length = edge_length_of(box, edge)
        offset_value = self.anchor.offset.value
        if offset_value > max_length + OFFSET_TOLERANCE_MM:
            raise ValueError(
                f"Offset {offset_value}mm exceeds piece dimension {max_length}mm "
                f"(piece '{self.piece.id}', edge {self.anchor.contact_face}/"
                f"{self.anchor.edge_shared_face})"
            )
        return self

    @classmethod
    def of(cls, piece: Piece, anchor: Anchor) -> "BoundAnchor":
        """Create a BoundAnchor instance.

        Args:
            piece: The piece this anchor belongs to
            anchor: The anchor position specification

        Returns:
            BoundAnchor instance

        Raises:
            ValueError: If the anchor's offset exceeds piece dimensions
        """
        return cls(piece=piece, anchor=anchor)


def _get_box(bound: BoundAnchor) -> Box:
    """Get the Box for a BoundAnchor's piece."""
    return Box(shape=get_shape(bound.piece))


def as_surface_point(bound: BoundAnchor) -> SurfacePoint:
    """Convert a bound anchor to a surface point.

    Args:
        bound: The bound anchor to convert

    Returns:
        SurfacePoint representing the anchor's position on the piece surface
    """
    box = _get_box(bound)
    return SurfacePoint.of(box, bound.anchor.contact_face, as_edge_point(bound.anchor))


def as_point_3d(bound: BoundAnchor) -> Point3D:
    """Convert a bound anchor to a 3D point.

    Args:
        bound: The bound anchor to convert

    Returns:
        Point3D representing the anchor's position in 3D space
    """
    box = _get_box(bound)
    surface_point = as_surface_point(bound)
    return Point3D.of(box, surface_point)
