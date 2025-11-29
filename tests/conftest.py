"""Shared test fixtures and utilities.

This module provides common fixtures and helper functions used across
the test suite to reduce code duplication.
"""

import pytest
from click.testing import CliRunner

from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.geometry import FromMax, FromMin, Offset
from nichiyou_daiku.core.piece import Piece, PieceType


# =============================================================================
# CLI Fixtures
# =============================================================================


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


# =============================================================================
# DSL Content Fixtures
# =============================================================================


@pytest.fixture
def simple_dsl() -> str:
    """Simple DSL content for testing (3 pieces with connection)."""
    return """
(leg1:2x4 {"length": 720})
(leg2:2x4 {"length": 720})
(apron:1x4 {"length": 600})

leg1 -[{"contact_face": "front", "edge_shared_face": "right", "offset": FromMax(100)}
       {"contact_face": "left", "edge_shared_face": "down", "offset": FromMin(0)}]- apron
"""


@pytest.fixture
def compact_dsl() -> str:
    """Simple DSL content using compact notation."""
    return """
(piece1:2x4 =1000)
(piece2:2x4 =800)

piece1 -[TF<0 BD<0]- piece2
"""


@pytest.fixture
def valid_dsl() -> str:
    """Valid DSL content with JSON format."""
    return """
(piece1:2x4 {"length": 1000})
(piece2:1x4 {"length": 800})

piece1 -[{"contact_face": "top", "edge_shared_face": "front", "offset": FromMin(0)}
         {"contact_face": "down", "edge_shared_face": "left", "offset": FromMax(100)}]- piece2
"""


@pytest.fixture
def invalid_syntax_dsl() -> str:
    """DSL with syntax error."""
    return """
(piece1:INVALID_TYPE {"length": 1000})
"""


@pytest.fixture
def invalid_semantic_dsl() -> str:
    """DSL with semantic error."""
    return """
(piece1:2x4 {"length": 1000})

piece1 -[{"contact_face": "top", "edge_shared_face": "front", "offset": FromMin(0)}
         {"contact_face": "down", "edge_shared_face": "left", "offset": FromMax(100)}]- unknown_piece
"""


# =============================================================================
# Test Helpers (not fixtures, but shared utility functions)
# =============================================================================


def create_bound_anchor(
    piece_id: str = "test",
    length: float = 1000.0,
    contact_face: str = "front",
    edge_shared_face: str = "right",
    offset: Offset | None = None,
    offset_type: str = "min",
    offset_value: float = 0.0,
    piece_type: PieceType = PieceType.PT_2x4,
) -> BoundAnchor:
    """Create a BoundAnchor for testing.

    This is a unified helper that supports both common use patterns:
    - Providing an Offset object directly
    - Specifying offset_type ("min" or "max") and offset_value

    Args:
        piece_id: ID for the piece
        length: Piece length in mm
        contact_face: Face that makes contact
        edge_shared_face: Face that shares the edge
        offset: Pre-created Offset object (takes precedence if provided)
        offset_type: "min" for FromMin, "max" for FromMax
        offset_value: Offset value in mm
        piece_type: Type of piece (default: 2x4)

    Returns:
        BoundAnchor instance
    """
    piece = Piece.of(piece_type, length, piece_id)

    if offset is None:
        offset = (
            FromMin(value=offset_value)
            if offset_type == "min"
            else FromMax(value=offset_value)
        )

    anchor = Anchor(
        contact_face=contact_face,
        edge_shared_face=edge_shared_face,
        offset=offset,
    )
    return BoundAnchor(piece=piece, anchor=anchor)
