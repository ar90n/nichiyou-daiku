"""Tests for the DSL parser."""

import pytest

from nichiyou_daiku.core.piece import PieceType
from nichiyou_daiku.dsl import (
    DSLSemanticError,
    DSLSyntaxError,
    DSLValidationError,
    parse_dsl,
)
from nichiyou_daiku.dsl.parser import DSLParser


class TestBasicParsing:
    """Test basic DSL parsing functionality."""

    def test_parse_single_piece_without_id(self):
        """Test parsing a single piece without an ID."""
        dsl = '(:2x4 {"length": 1000})'
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
        dsl = '(beam1:2x4 {"length": 1500})'
        model = parse_dsl(dsl)

        assert len(model.pieces) == 1
        piece = model.pieces["beam1"]
        assert piece.id == "beam1"
        assert piece.type == PieceType.PT_2x4
        assert piece.length == 1500.0

    def test_parse_multiple_pieces(self):
        """Test parsing multiple pieces."""
        dsl = """
        (beam1:2x4 {"length": 1000})
        (beam2:2x4 {"length": 2000})
        (board1:1x4 {"length": 800})
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
        (beam1:2x4 {"length": 1000})
        (beam2:2x4 {"length": 1000})
        beam1 -[{"contact_face": "front", "edge_shared_face": "top", "offset": FromMax(80)}
              {"contact_face": "down", "edge_shared_face": "front", "offset": FromMin(50)}]- beam2
        """
        model = parse_dsl(dsl)

        assert len(model.pieces) == 2
        assert len(model.connections) == 1

        # Check connection
        # model.connections is a dict with (base_id, target_id) as keys
        assert ("beam1", "beam2") in model.connections
        connection = model.connections[("beam1", "beam2")]

        # Check anchors
        assert connection.base.anchor.contact_face == "front"
        assert connection.base.anchor.edge_shared_face == "top"
        assert connection.base.anchor.offset.value == 80.0

        assert connection.target.anchor.contact_face == "down"
        assert connection.target.anchor.edge_shared_face == "front"
        assert connection.target.anchor.offset.value == 50.0


class TestSyntaxErrors:
    """Test syntax error handling."""

    def test_invalid_piece_type(self):
        """Test error on invalid piece type."""
        dsl = '(beam1:2x6 {"length": 1000})'
        with pytest.raises(DSLSyntaxError) as exc_info:
            parse_dsl(dsl)
        assert "Unexpected token" in str(exc_info.value)

    def test_missing_length_property(self):
        """Test error when length property is missing."""
        dsl = "(beam1:2x4 {})"
        with pytest.raises(Exception) as exc_info:
            parse_dsl(dsl)
        assert "length" in str(exc_info.value)

    def test_malformed_connection(self):
        """Test error on malformed connection syntax."""
        dsl = """
        (beam1:2x4 {"length": 1000})
        (beam2:2x4 {"length": 1000})
        beam1 - beam2
        """
        with pytest.raises(DSLSyntaxError):
            parse_dsl(dsl)

    def test_duplicate_piece_id(self):
        """Test error on duplicate piece IDs."""
        dsl = """
        (beam1:2x4 {"length": 1000})
        (beam1:2x4 {"length": 2000})
        """
        with pytest.raises(Exception) as exc_info:
            parse_dsl(dsl)
        assert "Duplicate piece ID" in str(exc_info.value)

    def test_unknown_piece_reference(self):
        """Test error on unknown piece reference in connection."""
        dsl = """
        (beam1:2x4 {"length": 1000})
        beam1 -[{"contact_face": "front", "edge_shared_face": "top", "offset": FromMax(80)}
              {"contact_face": "down", "edge_shared_face": "front", "offset": FromMin(50)}]- beam2
        """
        with pytest.raises(Exception) as exc_info:
            parse_dsl(dsl)
        assert "Unknown piece reference" in str(exc_info.value)


class TestCompactNotation:
    """Test compact notation parsing functionality."""

    def test_parse_simple_compact_connection(self):
        """Test parsing a simple connection with compact notation."""
        dsl = """
        (beam1:2x4 {"length": 1000})
        (beam2:2x4 {"length": 800})
        beam1 -[TF<0 BD<0]- beam2
        """
        model = parse_dsl(dsl)

        assert len(model.pieces) == 2
        assert len(model.connections) == 1

        # Check the connection was created correctly
        conn_key = ("beam1", "beam2")
        assert conn_key in model.connections
        connection = model.connections[conn_key]

        # Check anchors were transformed correctly
        assert connection.base.anchor.contact_face == "top"
        assert connection.base.anchor.edge_shared_face == "front"
        assert connection.base.anchor.offset.value == 0.0

        assert connection.target.anchor.contact_face == "back"
        assert connection.target.anchor.edge_shared_face == "down"
        assert connection.target.anchor.offset.value == 0.0

    def test_parse_compact_with_various_faces(self):
        """Test parsing compact notation with all face types."""
        dsl = """
        (p1:2x4 {"length": 500})
        (p2:2x4 {"length": 500})
        (p3:2x4 {"length": 500})
        (p4:2x4 {"length": 500})
        (p5:2x4 {"length": 500})
        (p6:2x4 {"length": 500})
        
        p1 -[TL<10 DR>20]- p2
        p3 -[FD<30 LT>35]- p4
        p5 -[RD<25 BD>60]- p6
        """
        model = parse_dsl(dsl)

        assert len(model.pieces) == 6
        assert len(model.connections) == 3

        # Check first connection (T/L and D/R)
        conn1 = model.connections[("p1", "p2")]
        assert conn1.base.anchor.contact_face == "top"
        assert conn1.base.anchor.edge_shared_face == "left"
        assert conn1.base.anchor.offset.value == 10.0
        assert conn1.target.anchor.contact_face == "down"
        assert conn1.target.anchor.edge_shared_face == "right"
        assert conn1.target.anchor.offset.value == 20.0

        # Check second connection (F/D and L/T)
        conn2 = model.connections[("p3", "p4")]
        assert conn2.base.anchor.contact_face == "front"
        assert conn2.base.anchor.edge_shared_face == "down"
        assert conn2.base.anchor.offset.value == 30.0
        assert conn2.target.anchor.contact_face == "left"
        assert conn2.target.anchor.edge_shared_face == "top"
        assert conn2.target.anchor.offset.value == 35.0

    def test_parse_mixed_notation_error(self):
        """Test error when mixing compact and JSON notation."""
        dsl = """
        (beam1:2x4 {"length": 1000})
        (beam2:2x4 {"length": 800})
        beam1 -[TF<0 {"contact_face": "back", "edge_shared_face": "down", "offset": FromMin(0)}]- beam2
        """
        with pytest.raises(DSLSyntaxError):
            parse_dsl(dsl)

    def test_parse_invalid_compact_face(self):
        """Test error on invalid compact face notation."""
        dsl = """
        (beam1:2x4 {"length": 1000})
        (beam2:2x4 {"length": 800})
        beam1 -[XF<0 BD<0]- beam2
        """
        with pytest.raises(DSLSyntaxError):
            parse_dsl(dsl)
        # Should fail at parse time due to regex not matching

    def test_parse_compact_with_float_offset(self):
        """Test parsing compact notation with floating point offsets."""
        dsl = """
        (beam1:2x4 {"length": 1000})
        (beam2:2x4 {"length": 800})
        beam1 -[TF<12.5 BD>37.8]- beam2
        """
        model = parse_dsl(dsl)

        connection = model.connections[("beam1", "beam2")]
        assert connection.base.anchor.offset.value == 12.5
        assert connection.target.anchor.offset.value == 37.8


class TestCompactPieceNotation:
    """Test compact piece notation functionality."""

    def test_parse_simple_compact_piece(self):
        """Test parsing a piece with compact length notation."""
        dsl = "(beam1:2x4 =1000)"
        model = parse_dsl(dsl)

        assert len(model.pieces) == 1
        piece = model.pieces["beam1"]
        assert piece.type == PieceType.PT_2x4
        assert piece.length == 1000.0

    def test_parse_multiple_compact_pieces(self):
        """Test parsing multiple pieces with compact notation."""
        dsl = """
        (beam1:2x4 =1000)
        (beam2:2x4 =800)
        (board1:1x4 =600)
        """
        model = parse_dsl(dsl)

        assert len(model.pieces) == 3
        assert model.pieces["beam1"].length == 1000.0
        assert model.pieces["beam2"].length == 800.0
        assert model.pieces["board1"].length == 600.0

    def test_parse_compact_piece_without_id(self):
        """Test parsing compact piece without ID."""
        dsl = "(:2x4 =1500)"
        model = parse_dsl(dsl)

        assert len(model.pieces) == 1
        piece = list(model.pieces.values())[0]
        assert piece.length == 1500.0
        # ID should be auto-generated
        assert len(piece.id) == 36

    def test_parse_mixed_piece_notation(self):
        """Test parsing with both compact and JSON notation."""
        dsl = """
        (beam1:2x4 =1000)
        (beam2:2x4 {"length": 2000})
        (beam3:2x4 =1500)
        """
        model = parse_dsl(dsl)

        assert len(model.pieces) == 3
        assert model.pieces["beam1"].length == 1000.0
        assert model.pieces["beam2"].length == 2000.0
        assert model.pieces["beam3"].length == 1500.0

    def test_parse_compact_piece_with_float(self):
        """Test parsing compact notation with floating point lengths."""
        dsl = """
        (beam1:2x4 =1000.5)
        (beam2:2x4 =800.75)
        """
        model = parse_dsl(dsl)

        assert model.pieces["beam1"].length == 1000.5
        assert model.pieces["beam2"].length == 800.75

    def test_parse_compact_piece_with_connection(self):
        """Test parsing compact pieces with connections."""
        dsl = """
        (beam1:2x4 =1000)
        (beam2:2x4 =800)
        beam1 -[TF<0 BD<0]- beam2
        """
        model = parse_dsl(dsl)

        assert len(model.pieces) == 2
        assert len(model.connections) == 1
        assert model.pieces["beam1"].length == 1000.0
        assert model.pieces["beam2"].length == 800.0


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_dsl(self):
        """Test parsing empty DSL."""
        with pytest.raises(DSLSyntaxError):
            parse_dsl("")

    def test_whitespace_handling(self):
        """Test that whitespace is properly handled."""
        dsl = """
        
        (beam1:2x4    {"length": 1000})
        
        (beam2:2x4 {"length":    2000   })
        
        """
        model = parse_dsl(dsl)
        assert len(model.pieces) == 2

    def test_string_escaping(self):
        """Test string escaping in properties."""
        dsl = '(beam1:2x4 {"length": 1000, "note": "Test \\"quoted\\" string"})'
        model = parse_dsl(dsl)
        assert len(model.pieces) == 1
        # Note: current implementation only uses length, but parsing should not fail

    def test_debug_mode(self):
        """Test parser in debug mode."""
        dsl = '(beam1:2x4 {"length": 1000})'
        # Should not raise an exception
        model = parse_dsl(dsl, debug=True)
        assert len(model.pieces) == 1


class TestPropertyValidation:
    """Test validation of JSON property objects."""

    ANCHOR = (
        '{"contact_face": "back", "edge_shared_face": "down", "offset": FromMin(0)}'
    )

    def connection(self, first_anchor: str) -> str:
        return f"""
        (a:2x4 =1000)
        (b:2x4 =800)
        a -[{first_anchor} {self.ANCHOR}]- b
        """

    @pytest.mark.parametrize(
        "length", ['"720"', "FromMin(720)"], ids=["string", "offset"]
    )
    def test_non_numeric_length_rejected(self, length):
        """Test that a piece length must be a number."""
        with pytest.raises(DSLValidationError, match="'length' must be a number"):
            parse_dsl(f'(a:2x4 {{"length": {length}}})')

    @pytest.mark.parametrize(
        "props,key",
        [
            ('{"lenght": 720}', "lenght"),
            ('{"length": 720, "colour": "red"}', "colour"),
        ],
    )
    def test_unknown_piece_property_rejected(self, props, key):
        """Test that misspelt or unsupported piece keys are rejected."""
        with pytest.raises(DSLValidationError, match=f"Unknown piece property '{key}'"):
            parse_dsl(f"(a:2x4 {props})")

    def test_unknown_anchor_property_rejected(self):
        """Test that misspelt anchor keys are rejected, not ignored."""
        anchor = (
            '{"contct_face": "top", "contact_face": "top", '
            '"edge_shared_face": "front", "offset": FromMin(0)}'
        )
        with pytest.raises(
            DSLValidationError, match="Unknown anchor property 'contct_face'"
        ):
            parse_dsl(self.connection(anchor))

    def test_duplicate_piece_property_rejected(self):
        """Test that a repeated key is rejected instead of last-wins."""
        with pytest.raises(DSLValidationError, match="Duplicate property 'length'"):
            parse_dsl('(a:2x4 {"length": 720, "length": 10})')

    def test_duplicate_anchor_property_rejected(self):
        """Test that a repeated anchor key is rejected instead of last-wins."""
        anchor = (
            '{"contact_face": "top", "contact_face": "down", '
            '"edge_shared_face": "front", "offset": FromMin(0)}'
        )
        with pytest.raises(
            DSLValidationError, match="Duplicate property 'contact_face'"
        ):
            parse_dsl(self.connection(anchor))

    def test_zero_length_in_json_rejected(self):
        """Test that the core zero-length check surfaces readably."""
        with pytest.raises(DSLValidationError) as exc_info:
            parse_dsl('(a:2x4 {"length": 0})')
        assert "length" in str(exc_info.value)
        assert "greater than 0" in str(exc_info.value)
        assert "validation error for" not in str(exc_info.value)

    def test_note_property_allowed(self):
        """Test that the documented free-form note is still accepted."""
        model = parse_dsl('(a:2x4 {"length": 720, "note": "front apron"})')
        assert model.pieces["a"].length == 720.0


class TestParserReuse:
    """Test that a parser instance can be reused safely."""

    DSL = """
    (a:2x4 =1000)
    (b:2x4 =800)
    a -[TF<0 BD<0]- b
    """

    def test_parse_twice_with_same_parser(self):
        """Test that parsing twice does not report duplicate pieces."""
        parser = DSLParser()

        first = parser.parse(self.DSL)
        second = parser.parse(self.DSL)

        assert first == second
        assert len(second.pieces) == 2
        assert len(second.connections) == 1

    def test_failed_parse_does_not_leak_into_next_parse(self):
        """Test that pieces from a failed parse are not kept."""
        parser = DSLParser()
        with pytest.raises(DSLSemanticError):
            parser.parse("(a:2x4 =1000)\na -[TF<0 BD<0]- missing")

        model = parser.parse("(a:2x4 =500)")

        assert list(model.pieces) == ["a"]
        assert model.pieces["a"].length == 500.0

    def test_grammar_is_built_once(self):
        """Test that parsers share one compiled Lark instance."""
        assert DSLParser()._parser is DSLParser()._parser
