"""DSL-specific exception classes."""


class DSLError(Exception):
    """Base class for all DSL-related errors.

    Attributes:
        message: The error description without location information.
        line: 1-based line of the offending source, if known.
        column: 1-based column of the offending source, if known.

    Examples:
        >>> str(DSLError("Unknown piece reference: x", line=3, column=5))
        'line 3, column 5: Unknown piece reference: x'
        >>> str(DSLError("Unknown piece reference: x"))
        'Unknown piece reference: x'
    """

    def __init__(
        self, message: str, line: int | None = None, column: int | None = None
    ):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(self._format(message, line, column))

    @staticmethod
    def _format(message: str, line: int | None, column: int | None) -> str:
        if line is not None and column is not None:
            return f"line {line}, column {column}: {message}"
        if line is not None:
            return f"line {line}: {message}"
        return message


class DSLSyntaxError(DSLError):
    """Raised when the DSL syntax is invalid."""

    @staticmethod
    def _format(message: str, line: int | None, column: int | None) -> str:
        if line is not None and column is not None:
            return f"Syntax error at line {line}, column {column}: {message}"
        if line is not None:
            return f"Syntax error at line {line}: {message}"
        return f"Syntax error: {message}"


class DSLSemanticError(DSLError):
    """Raised when the DSL is syntactically valid but semantically incorrect."""


class DSLValidationError(DSLError):
    """Raised when DSL values fail validation."""
