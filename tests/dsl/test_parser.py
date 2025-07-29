"""Tests for the DSL parser."""

import pytest

from nichiyou_daiku.core.piece import PieceType
from nichiyou_daiku.dsl import DSLSyntaxError, parse_dsl


class TestBasicParsing:
    """Test basic DSL parsing functionality."""

    def test_parse_single_piece_without_id(self):
        """Test parsing a single piece without an ID."""
        dsl = '(:PT_2x4 {"length": 1000})'
        model = parse_dsl(dsl)

        assert len(model.pieces) == 1
        piece = list(model.pieces.values())[0]
        assert piece.type == PieceType.PT_2x4
        assert piece.length == 1000.0
        # ID should be auto-generated (UUID format)
        assert len(piece.id) == 36
        assert "-" in piece.id

    def test_parse_single_piece_with_id(self):
        """Test parsing a single piece with a custom ID."""
        dsl = '(beam1:PT_2x4 {"length": 1500})'
        model = parse_dsl(dsl)

        assert len(model.pieces) == 1
        piece = model.pieces["beam1"]
        assert piece.id == "beam1"
        assert piece.type == PieceType.PT_2x4
        assert piece.length == 1500.0

    def test_parse_multiple_pieces(self):
        """Test parsing multiple pieces."""
        dsl = """
        (beam1:PT_2x4 {"length": 1000})
        (beam2:PT_2x4 {"length": 2000})
        (board1:PT_1x4 {"length": 800})
        """
        model = parse_dsl(dsl)

        assert len(model.pieces) == 3

        # Check pieces by ID (model.pieces is already a dict)
        assert "beam1" in model.pieces
        assert "beam2" in model.pieces
        assert "board1" in model.pieces

        assert model.pieces["beam1"].length == 1000.0
        assert model.pieces["beam2"].length == 2000.0
        assert model.pieces["board1"].type == PieceType.PT_1x4

    def test_parse_piece_with_connection(self):
        """Test parsing pieces with a connection."""
        dsl = """
        (beam1:PT_2x4 {"length": 1000})
        (beam2:PT_2x4 {"length": 1000})
        beam1 -[{"contact_face": "front", "edge_shared_face": "top", "offset": FromMax(100)}
              {"contact_face": "bottom", "edge_shared_face": "front", "offset": FromMin(50)}]- beam2
        """
        model = parse_dsl(dsl)

        assert len(model.pieces) == 2
        assert len(model.connections) == 1

        # Check connection
        # model.connections is a dict with (base_id, target_id) as keys
        assert ("beam1", "beam2") in model.connections
        connection = model.connections[("beam1", "beam2")]

        # Check anchors
        assert connection.lhs.contact_face == "front"
        assert connection.lhs.edge_shared_face == "top"
        assert connection.lhs.offset.value == 100.0

        assert connection.rhs.contact_face == "bottom"
        assert connection.rhs.edge_shared_face == "front"
        assert connection.rhs.offset.value == 50.0


class TestSyntaxErrors:
    """Test syntax error handling."""

    def test_invalid_piece_type(self):
        """Test error on invalid piece type."""
        dsl = '(beam1:PT_2x6 {"length": 1000})'
        with pytest.raises(DSLSyntaxError) as exc_info:
            parse_dsl(dsl)
        assert "Unexpected token" in str(exc_info.value)

    def test_missing_length_property(self):
        """Test error when length property is missing."""
        dsl = "(beam1:PT_2x4 {})"
        with pytest.raises(Exception) as exc_info:
            parse_dsl(dsl)
        assert "length" in str(exc_info.value)

    def test_malformed_connection(self):
        """Test error on malformed connection syntax."""
        dsl = """
        (beam1:PT_2x4 {"length": 1000})
        (beam2:PT_2x4 {"length": 1000})
        beam1 - beam2
        """
        with pytest.raises(DSLSyntaxError):
            parse_dsl(dsl)

    def test_duplicate_piece_id(self):
        """Test error on duplicate piece IDs."""
        dsl = """
        (beam1:PT_2x4 {"length": 1000})
        (beam1:PT_2x4 {"length": 2000})
        """
        with pytest.raises(Exception) as exc_info:
            parse_dsl(dsl)
        assert "Duplicate piece ID" in str(exc_info.value)

    def test_unknown_piece_reference(self):
        """Test error on unknown piece reference in connection."""
        dsl = """
        (beam1:PT_2x4 {"length": 1000})
        beam1 -[{"contact_face": "front", "edge_shared_face": "top", "offset": FromMax(100)}
              {"contact_face": "bottom", "edge_shared_face": "front", "offset": FromMin(50)}]- beam2
        """
        with pytest.raises(Exception) as exc_info:
            parse_dsl(dsl)
        assert "Unknown piece reference" in str(exc_info.value)


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_dsl(self):
        """Test parsing empty DSL."""
        with pytest.raises(DSLSyntaxError):
            parse_dsl("")

    def test_whitespace_handling(self):
        """Test that whitespace is properly handled."""
        dsl = """
        
        (beam1:PT_2x4    {"length": 1000})
        
        (beam2:PT_2x4 {"length":    2000   })
        
        """
        model = parse_dsl(dsl)
        assert len(model.pieces) == 2

    def test_string_escaping(self):
        """Test string escaping in properties."""
        dsl = '(beam1:PT_2x4 {"length": 1000, "note": "Test \\"quoted\\" string"})'
        model = parse_dsl(dsl)
        assert len(model.pieces) == 1
        # Note: current implementation only uses length, but parsing should not fail

    def test_debug_mode(self):
        """Test parser in debug mode."""
        dsl = '(beam1:PT_2x4 {"length": 1000})'
        # Should not raise an exception
        model = parse_dsl(dsl, debug=True)
        assert len(model.pieces) == 1
