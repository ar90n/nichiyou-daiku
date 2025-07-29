"""DSL-specific exception classes."""


class DSLError(Exception):
    """Base class for all DSL-related errors."""

    pass


class DSLSyntaxError(DSLError):
    """Raised when the DSL syntax is invalid."""

    def __init__(
        self, message: str, line: int | None = None, column: int | None = None
    ):
        self.line = line
        self.column = column
        if line is not None and column is not None:
            super().__init__(f"Syntax error at line {line}, column {column}: {message}")
        elif line is not None:
            super().__init__(f"Syntax error at line {line}: {message}")
        else:
            super().__init__(f"Syntax error: {message}")


class DSLSemanticError(DSLError):
    """Raised when the DSL is syntactically valid but semantically incorrect."""

    pass


class DSLValidationError(DSLError):
    """Raised when DSL values fail validation."""

    pass
