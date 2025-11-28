"""DSL parser using Lark."""

from lark import Lark, ParseError, UnexpectedInput
from lark.exceptions import VisitError

from nichiyou_daiku.core.model import Model
from nichiyou_daiku.dsl.exceptions import DSLSyntaxError, DSLSemanticError, DSLValidationError
from nichiyou_daiku.dsl.grammar import GRAMMAR
from nichiyou_daiku.dsl.transformer import DSLTransformer


class DSLParser:
    """Parser for the nichiyou-daiku DSL."""

    def __init__(self, debug: bool = False):
        """Initialize the parser.

        Args:
            debug: If True, enables debug mode for the parser.
        """
        self.debug = debug
        self._parser = Lark(
            GRAMMAR,
            parser="lalr",
            debug=debug,
            propagate_positions=True,
        )
        self._transformer = DSLTransformer()

    def parse(self, dsl_string: str) -> Model:
        """Parse a DSL string and return a Model instance.

        Args:
            dsl_string: The DSL string to parse.

        Returns:
            A Model instance representing the parsed DSL.

        Raises:
            DSLSyntaxError: If the DSL syntax is invalid.
        """
        try:
            tree = self._parser.parse(dsl_string)
            if self.debug:
                print("Parse tree:")
                print(tree.pretty())
            return self._transformer.transform(tree)
        except UnexpectedInput as e:
            raise DSLSyntaxError(
                str(e),
                line=e.line,
                column=e.column,
            )
        except ParseError as e:
            raise DSLSyntaxError(str(e))
        except VisitError as e:
            # Extract the actual error from the VisitError
            if e.orig_exc and isinstance(e.orig_exc, (DSLSemanticError, DSLValidationError)):
                raise e.orig_exc
            else:
                raise DSLSemanticError(str(e))


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
