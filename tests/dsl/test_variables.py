"""Tests for DSL variables and arithmetic expressions."""

from pathlib import Path

import pytest

from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.connection import DowelConnection, ScrewConnection
from nichiyou_daiku.core.geometry import FromMax, FromMin
from nichiyou_daiku.core.placement import find_overlaps
from nichiyou_daiku.dsl import (
    DSLSemanticError,
    DSLSyntaxError,
    DSLValidationError,
    parse_dsl,
)

EXAMPLES = Path(__file__).parents[2] / "examples" / "nd_files"


def _length(source: str, piece_id: str = "a") -> float:
    return parse_dsl(source).pieces[piece_id].length


def _connection(source: str):
    return next(iter(parse_dsl(source).connections.values()))


class TestExpressions:
    def test_variable_sets_a_length(self):
        assert _length("W = 600\n(a:2x4 =W)") == 600.0

    @pytest.mark.parametrize(
        ("expression", "value"),
        [
            ("2 + 3 * 4", 14.0),
            ("(2 + 3) * 4", 20.0),
            ("100 - 10 - 5", 85.0),
            ("600 / 4 / 2", 75.0),
            ("10 - -2", 12.0),
            ("-(5 - 15)", 10.0),
            ("2.5 * 4", 10.0),
        ],
    )
    def test_arithmetic_follows_the_usual_precedence(self, expression, value):
        assert _length(f"(a:2x4 ={expression})") == value

    def test_variables_build_on_earlier_variables(self):
        source = "W = 800\nLEG = 89\nAPRON = W - 2 * LEG\n(a:2x4 =APRON)"
        assert _length(source) == 622.0

    def test_json_length_accepts_an_expression(self):
        assert _length('H = 720\n(a:2x4 {"length": H - 19})') == 701.0


PIECES = "(a:2x4 =1000)\n(b:2x4 =800)\n"


class TestExpressionsInConnections:
    @pytest.mark.parametrize(
        ("offset", "expected"),
        [
            ("<X", FromMin(value=300.0)),
            (">X", FromMax(value=300.0)),
            ("<(X / 2)", FromMin(value=150.0)),
            ("<(X - 1)", FromMin(value=299.0)),
            ("<25", FromMin(value=25.0)),
        ],
    )
    def test_compact_offset_takes_a_number_variable_or_bracketed_expression(
        self, offset, expected
    ):
        connection = _connection(f"X = 300\n{PIECES}a -[FL{offset} DF<0]- b")
        assert connection.base.anchor.offset == expected

    def test_json_offset_accepts_an_expression(self):
        source = (
            f"X = 300\n{PIECES}a -["
            '{"contact_face": "front", "edge_shared_face": "left", '
            '"offset": FromMax(X + 50)}'
            '{"contact_face": "down", "edge_shared_face": "front", '
            '"offset": FromMin(0)}]- b'
        )
        assert _connection(source).base.anchor.offset == FromMax(value=350.0)

    def test_numeric_dowel_and_screw_accept_expressions(self):
        dowel = _connection(f"R = 4\nL = 30\n{PIECES}a -[FL<0 DF<0 D(R, L)]- b")
        assert dowel.type == DowelConnection(radius=4.0, depth=30.0)

        screw = _connection(f"L = 50\n{PIECES}a -[FL<0 BL<0 S(3.5, L + 10)]- b")
        assert screw.type == ScrewConnection(diameter=3.5, length=60.0)

    def test_json_dowel_accepts_expressions(self):
        source = (
            f"R = 4\n{PIECES}a -["
            '{"contact_face": "front", "edge_shared_face": "left", '
            '"offset": FromMin(0)}'
            '{"contact_face": "down", "edge_shared_face": "front", '
            '"offset": FromMin(0)}'
            '{"type": "dowel", "radius": R, "depth": R * 7}]- b'
        )
        assert _connection(source).type == DowelConnection(radius=4.0, depth=28.0)

    def test_presets_are_unchanged(self):
        connection = _connection(f"{PIECES}a -[FL<0 DF<0 D(:8x30)]- b")
        assert connection.type == DowelConnection(radius=4.0, depth=30.0)

    def test_variable_may_share_a_name_with_a_face_letter(self):
        connection = _connection(f"T = 50\n{PIECES}a -[FL<T DF<0]- b")
        assert connection.base.anchor.offset == FromMin(value=50.0)


class TestErrors:
    def test_undefined_variable_is_located(self):
        with pytest.raises(DSLSemanticError, match="Undefined variable 'W'") as exc:
            parse_dsl("(a:2x4 =1000)\n(b:2x4 =W)")
        assert (exc.value.line, exc.value.column) == (2, 9)

    def test_variable_must_be_defined_before_use(self):
        with pytest.raises(DSLSemanticError, match="Undefined variable 'W'"):
            parse_dsl("(a:2x4 =W)\nW = 600")

    def test_variable_cannot_be_redefined(self):
        with pytest.raises(DSLSemanticError, match="'W' is already defined") as exc:
            parse_dsl("W = 600\nW = 700\n(a:2x4 =W)")
        assert exc.value.line == 2

    def test_division_by_zero_is_reported(self):
        with pytest.raises(DSLValidationError, match="Division by zero"):
            parse_dsl("ZERO = 0\n(a:2x4 =600 / ZERO)")

    def test_compact_offset_expression_needs_brackets(self):
        with pytest.raises(DSLSyntaxError):
            parse_dsl(f"X = 300\n{PIECES}a -[FL<X - 1 DF<0]- b")

    def test_invalid_result_is_caught_by_the_usual_validation(self):
        with pytest.raises(DSLValidationError):
            parse_dsl("W = 100\n(a:2x4 =W - 100)")


class TestParametricExample:
    def test_parametric_table_matches_the_compact_table(self):
        parametric = parse_dsl((EXAMPLES / "simple_table_parametric.nd").read_text())
        compact = parse_dsl((EXAMPLES / "simple_table_compact.nd").read_text())

        def lengths(model):
            return {pid: piece.length for pid, piece in model.pieces.items()}

        assert lengths(parametric) == lengths(compact)

    def test_parametric_table_is_valid(self):
        model = parse_dsl((EXAMPLES / "simple_table_parametric.nd").read_text())
        assembly = Assembly.of(model)
        assert assembly.placement.conflicts == ()
        assert len(assembly.placement.groups) == 1
        assert find_overlaps(model, assembly.placement) == ()
