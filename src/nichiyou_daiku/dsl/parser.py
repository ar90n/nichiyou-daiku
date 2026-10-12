"""DSL parser using Lark."""

import re
from functools import cache

from lark import (
    Lark,
    Token,
    Tree,
    UnexpectedCharacters,
    UnexpectedInput,
    UnexpectedToken,
)
from lark.exceptions import VisitError
from lark.lexer import PatternStr, TerminalDef
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from nichiyou_daiku.core.model import Model
from nichiyou_daiku.dsl.exceptions import (
    DSLError,
    DSLSyntaxError,
    DSLSemanticError,
    DSLValidationError,
)
from nichiyou_daiku.dsl.grammar import GRAMMAR, PIECE_TYPE_NAMES
from nichiyou_daiku.dsl.transformer import DSLTransformer


_COMMENT = re.compile(r"//[^\n]*")

_TERMINAL_DESCRIPTIONS = {
    "$END": "end of input",
    "CNAME": "identifier",
    "NUMBER": "number",
    "ESCAPED_STRING": "string",
    "PIECE_TYPE": f"piece type ({', '.join(PIECE_TYPE_NAMES)})",
    "COMPACT_FACE": "face letter (T, D, L, R, F, B)",
    "SCREW_TYPE": "screw type (Slim, Coarse)",
    "UNKNOWN": "'?' (unknown)",
}


@cache
def _build_parser(debug: bool) -> Lark:
    """Build the LALR parser once per debug setting; building it is costly."""
    return Lark(
        GRAMMAR,
        parser="lalr",
        debug=debug,
        propagate_positions=True,
    )


class DSLParser:
    """Parser for the nichiyou-daiku DSL."""

    def __init__(self, debug: bool = False):
        """Initialize the parser.

        Args:
            debug: If True, enables debug mode for the parser.
        """
        self.debug = debug
        self._parser = _build_parser(debug)

    def parse(self, dsl_string: str) -> Model:
        """Parse a DSL string and return a Model instance.

        Args:
            dsl_string: The DSL string to parse.

        Returns:
            A Model instance representing the parsed DSL.

        Raises:
            DSLSyntaxError: If the DSL syntax is invalid.
            DSLSemanticError: If the DSL is semantically incorrect.
            DSLValidationError: If DSL values fail validation.
        """
        if not _COMMENT.sub("", dsl_string).strip():
            raise DSLSyntaxError(
                "No pieces defined: the input is empty or contains only comments. "
                "Expected at least one piece definition such as (leg:2x4 =720)"
            )
        try:
            tree = self._parser.parse(dsl_string)
            if self.debug:
                print("Parse tree:")
                print(tree.pretty())
            # The transformer accumulates pieces, so each parse needs its own.
            return DSLTransformer().transform(tree)
        except UnexpectedInput as e:
            raise DSLSyntaxError(
                _describe_syntax_error(e, self._parser),
                line=e.line,
                column=e.column,
            ) from e
        except VisitError as e:
            raise _as_located_error(e) from e.orig_exc


_ARITHMETIC = {"+", "-", "*", "/"}


def _describe_syntax_error(error: UnexpectedInput, parser: Lark) -> str:
    """Describe a parse error using readable names for the expected input."""
    if isinstance(error, UnexpectedCharacters):
        found = f"Unexpected character {error.char!r}"
        expected = error.allowed or set()
    elif isinstance(error, UnexpectedToken) and error.token.type != "$END":
        found = f"Unexpected token {error.token.value!r}"
        expected = error.expected
    else:
        found = "Unexpected end of input"
        expected = getattr(error, "expected", None) or set()
    # LALR merges lookaheads across every place an expression may appear, so
    # ask the parser what it accepts at this exact point instead.
    state = getattr(error, "interactive_parser", None)
    if state is not None:
        expected = state.accepts()

    terminals = {terminal.name: terminal for terminal in parser.terminals}
    descriptions = sorted(
        {_describe_terminal(name, terminals.get(name)) for name in expected}
    )
    label = "Expected" if len(descriptions) == 1 else "Expected one of"
    message = f"{found}. {label}: {', '.join(descriptions)}" if descriptions else found
    if (
        isinstance(error, UnexpectedToken)
        and error.token.value in _ARITHMETIC
        and "COMPACT_FACE" in expected
    ):
        message += (
            ". A compact offset that is an expression needs parentheses, "
            "e.g. FL<(X + 1)"
        )
    return message


def _describe_terminal(name: str, terminal: TerminalDef | None) -> str:
    if name in _TERMINAL_DESCRIPTIONS:
        return _TERMINAL_DESCRIPTIONS[name]
    # Anonymous terminals (e.g. __ANON_0 for "-[") read best as their literal.
    if terminal is not None and isinstance(terminal.pattern, PatternStr):
        return repr(terminal.pattern.value)
    return name.lower()


def _as_located_error(error: VisitError) -> DSLError:
    """Convert an error raised while transforming a rule into a DSL error.

    The location is taken from the innermost rule being transformed, so it
    points at the offending statement (or anchor/preset within it).
    """
    line, column = _position_of(error.obj)
    orig = error.orig_exc
    match orig:
        case DSLError():
            # Errors found after the statements are read carry their own place
            return type(orig)(
                orig.message,
                orig.line if orig.line is not None else line,
                orig.column if orig.column is not None else column,
            )
        case ValidationError():
            return DSLValidationError(_describe_validation_error(orig), line, column)
        case ValueError():
            return DSLValidationError(str(orig), line, column)
        case _:
            # Not a user error, but keep the documented DSLError contract.
            return DSLSemanticError(str(orig), line, column)


def _position_of(node: Tree | Token) -> tuple[int | None, int | None]:
    # Only rule callbacks exist, so node is a Tree whose meta carries the
    # position (propagate_positions=True); an empty meta has no line/column.
    meta = getattr(node, "meta", None)
    return getattr(meta, "line", None), getattr(meta, "column", None)


def _describe_validation_error(error: ValidationError) -> str:
    """Render a pydantic error as its core messages, without boilerplate."""
    return "; ".join(_describe_error_detail(detail) for detail in error.errors())


def _describe_error_detail(detail: ErrorDetails) -> str:
    cause = detail.get("ctx", {}).get("error")
    if detail["type"] == "value_error" and cause is not None:
        return str(cause)
    field = ".".join(str(part) for part in detail["loc"])
    message = f"{detail['msg']} (got {detail['input']!r})"
    return f"{field}: {message}" if field else message


def parse_dsl(dsl_string: str, debug: bool = False) -> Model:
    """Parse a DSL string and return a Model instance.

    This is a convenience function that creates a parser and parses the string.

    Args:
        dsl_string: The DSL string to parse.
        debug: If True, enables debug mode for the parser.

    Returns:
        A Model instance representing the parsed DSL.

    Raises:
        DSLSyntaxError: If the DSL syntax is invalid.
        DSLSemanticError: If the DSL is semantically incorrect.
        DSLValidationError: If DSL values fail validation.
    """
    parser = DSLParser(debug=debug)
    return parser.parse(dsl_string)
