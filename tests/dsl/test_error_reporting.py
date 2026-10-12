"""Tests for DSL error locations and readable error messages."""

import pytest

from nichiyou_daiku.dsl import (
    DSLSemanticError,
    DSLSyntaxError,
    DSLValidationError,
    parse_dsl,
)
from nichiyou_daiku.dsl.transformer import DSLTransformer

PIECES = "(a:2x4 =1000)\n(b:2x4 =800)\n"

PYDANTIC_BOILERPLATE = ("validation error for", "Value error,", "errors.pydantic.dev")


def assert_readable(message: str) -> None:
    for fragment in PYDANTIC_BOILERPLATE + ("Error trying to process rule",):
        assert fragment not in message


class TestTransformErrorLocation:
    """Errors raised while building the model point at the offending source."""

    def test_non_adjacent_faces(self):
        """Core anchor validation surfaces as a located validation error."""
        dsl = PIECES + "\na -[TD<0 BD<0]- b\n"

        with pytest.raises(DSLValidationError) as exc_info:
            parse_dsl(dsl)

        error = exc_info.value
        assert error.line == 4
        assert error.column == 5
        assert str(error) == (
            "line 4, column 5: contact_face 'top' and edge_shared_face 'down' "
            "must be adjacent faces"
        )

    def test_non_adjacent_faces_in_json_anchor_points_at_the_anchor(self):
        """A multi-line JSON connection reports the line of the bad anchor."""
        dsl = PIECES + (
            'a -[{"contact_face": "top", "edge_shared_face": "front", '
            '"offset": FromMin(0)}\n'
            '    {"contact_face": "back", "edge_shared_face": "front", '
            '"offset": FromMin(0)}]- b\n'
        )

        with pytest.raises(DSLValidationError) as exc_info:
            parse_dsl(dsl)

        assert exc_info.value.line == 4
        assert "'back' and edge_shared_face 'front'" in str(exc_info.value)

    def test_offset_out_of_range(self):
        """BoundAnchor validation surfaces with the connection's line."""
        dsl = PIECES + "a -[TF<500 BD<0]- b\n"

        with pytest.raises(DSLValidationError) as exc_info:
            parse_dsl(dsl)

        message = str(exc_info.value)
        assert exc_info.value.line == 3
        assert message.startswith("line 3")
        assert "Offset 500.0mm exceeds piece dimension 89.0mm" in message
        assert_readable(message)

    def test_screw_too_short(self):
        """Connection validation surfaces with the connection's line."""
        dsl = PIECES + "\n\na -[FD<0 BT<0 S(3.3, 20)]- b\n"

        with pytest.raises(DSLValidationError) as exc_info:
            parse_dsl(dsl)

        message = str(exc_info.value)
        assert exc_info.value.line == 5
        assert "Screw length 20.0mm does not reach base piece" in message
        assert_readable(message)

    def test_self_connection(self):
        """Connecting a piece to itself is a located validation error."""
        dsl = PIECES + "a -[TF<0 BD<0]- a\n"

        with pytest.raises(DSLValidationError) as exc_info:
            parse_dsl(dsl)

        assert exc_info.value.line == 3
        assert "Piece 'a' cannot be connected to itself" in str(exc_info.value)

    def test_zero_length_piece(self):
        """Core piece validation surfaces as a readable validation error."""
        dsl = "(a:2x4 =1000)\n(b:2x4 =0)\n"

        with pytest.raises(DSLValidationError) as exc_info:
            parse_dsl(dsl)

        message = str(exc_info.value)
        assert exc_info.value.line == 2
        assert "length" in message
        assert "greater than 0" in message
        assert_readable(message)

    def test_invalid_face_name_in_json_anchor(self):
        """A misspelt face name names the field and the bad value."""
        dsl = PIECES + (
            'a -[{"contact_face": "tpo", "edge_shared_face": "front", '
            '"offset": FromMin(0)}\n'
            '    {"contact_face": "back", "edge_shared_face": "down", '
            '"offset": FromMin(0)}]- b\n'
        )

        with pytest.raises(DSLValidationError) as exc_info:
            parse_dsl(dsl)

        message = str(exc_info.value)
        assert exc_info.value.line == 3
        assert "contact_face" in message
        assert "'tpo'" in message
        assert_readable(message)

    def test_unknown_piece_reference(self):
        """Unknown references stay semantic errors and gain a location."""
        dsl = "(a:2x4 =600)\n\na -[FD<0 BT<0]- zz\n"

        with pytest.raises(DSLSemanticError) as exc_info:
            parse_dsl(dsl)

        assert exc_info.value.line == 3
        assert str(exc_info.value) == ("line 3, column 1: Unknown piece reference: zz")

    def test_duplicate_piece_id(self):
        """Duplicate ids report the line of the second definition."""
        dsl = "(a:2x4 =600)\n  (a:2x4 =700)\n"

        with pytest.raises(DSLSemanticError) as exc_info:
            parse_dsl(dsl)

        assert (exc_info.value.line, exc_info.value.column) == (2, 3)
        assert "Duplicate piece ID: a" in str(exc_info.value)

    def test_duplicate_connection(self):
        """A second connection for the same pair reports its own line."""
        dsl = PIECES + "a -[TF<0 BD<0]- b\na -[TF<10 BD<0]- b\n"

        with pytest.raises(DSLSemanticError) as exc_info:
            parse_dsl(dsl)

        message = str(exc_info.value)
        assert exc_info.value.line == 4
        assert "Duplicate connection between 'a' and 'b'" in message
        assert_readable(message)

    def test_duplicate_connection_in_reverse_direction(self):
        """b-a after a-b is the same piece pair."""
        dsl = PIECES + "a -[TF<0 BD<0]- b\nb -[BD<0 TF<0]- a\n"

        with pytest.raises(DSLSemanticError) as exc_info:
            parse_dsl(dsl)

        assert exc_info.value.line == 4
        assert "Duplicate connection between 'b' and 'a'" in str(exc_info.value)

    def test_unknown_preset(self):
        """Preset lookup errors carry the location of the preset."""
        dsl = PIECES + "a -[TF<0 BD<0 D(:9x99)]- b\n"

        with pytest.raises(DSLValidationError) as exc_info:
            parse_dsl(dsl)

        assert exc_info.value.line == 3
        assert "Unknown dowel preset: 9x99" in str(exc_info.value)


class TestSyntaxErrorMessages:
    """Syntax errors describe expected input without internal terminal names."""

    INTERNAL_NAMES = (
        "__ANON",
        "COMPACT_FACE",
        "DOWEL_START",
        "SCREW_START",
        "$END",
        "Token(",
        "LPAR",
        "RPAR",
        "LBRACE",
        "CNAME",
    )

    @pytest.mark.parametrize(
        "dsl",
        [
            PIECES + "a -[XF<0 BD<0]- b",
            PIECES + "a - b",
            PIECES + "a -[TF<0 BD<0 Q]- b",
            PIECES + "a -[TF<0 BD<0 D(8, )]- b",
            "(a:4x4 =100)",
            "(a:2x4 =100",
            "",
            "// only a comment\n",
        ],
    )
    def test_no_internal_terminal_names(self, dsl):
        """No lark-internal names leak into the message."""
        with pytest.raises(DSLSyntaxError) as exc_info:
            parse_dsl(dsl)

        message = str(exc_info.value)
        for name in self.INTERNAL_NAMES:
            assert name not in message

    def test_unexpected_token_lists_readable_alternatives(self):
        """The unexpected token and the readable alternatives are reported."""
        with pytest.raises(DSLSyntaxError) as exc_info:
            parse_dsl(PIECES + "a -[XF<0 BD<0]- b")

        assert str(exc_info.value) == (
            "Syntax error at line 3, column 5: Unexpected token 'XF'. "
            "Expected one of: '{', face letter (T, D, L, R, F, B)"
        )

    def test_unexpected_character(self):
        """A character no terminal matches is quoted with the alternatives."""
        with pytest.raises(DSLSyntaxError) as exc_info:
            parse_dsl(PIECES + "a -[TF<0 BD<0 @]- b")

        message = str(exc_info.value)
        assert "line 3" in message
        assert "Unexpected character '@'" in message
        assert "'D('" in message
        assert "']-'" in message

    def test_unexpected_end_of_input(self):
        """Truncated input reports the end of input and what was expected."""
        with pytest.raises(DSLSyntaxError) as exc_info:
            parse_dsl("(a:2x4 =100")

        message = str(exc_info.value)
        assert "Unexpected end of input" in message
        # The length may still continue as an expression
        assert message.endswith("Expected one of: ')', '+', '-'")

    @pytest.mark.parametrize("dsl", ["", "   \n\n", "// a\n  // b\n"])
    def test_empty_or_comment_only_input(self, dsl):
        """Input without statements reports that no pieces are defined."""
        with pytest.raises(DSLSyntaxError) as exc_info:
            parse_dsl(dsl)

        assert "No pieces defined" in str(exc_info.value)


class TestTransformErrorMapping:
    """Non-DSL exceptions from transformation become located DSL errors."""

    def test_plain_value_error_becomes_validation_error(self, monkeypatch):
        """A core ValueError keeps its text and gains the statement location."""

        def reject(self, items):
            raise ValueError("core rejected this piece")

        monkeypatch.setattr(DSLTransformer, "piece_def", reject)

        with pytest.raises(DSLValidationError) as exc_info:
            parse_dsl("\n  (a:2x4 =100)")

        assert str(exc_info.value) == "line 2, column 3: core rejected this piece"

    def test_unexpected_error_becomes_semantic_error(self, monkeypatch):
        """Any other exception is still reported as a DSL error."""

        def explode(self, items):
            raise RuntimeError("boom")

        monkeypatch.setattr(DSLTransformer, "piece_def", explode)

        with pytest.raises(DSLSemanticError) as exc_info:
            parse_dsl("(a:2x4 =100)")

        assert str(exc_info.value) == "line 1, column 1: boom"
