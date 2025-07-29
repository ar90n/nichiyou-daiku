"""Tests for DSL exception classes."""

import pytest

from nichiyou_daiku.dsl.exceptions import (
    DSLError,
    DSLSemanticError,
    DSLSyntaxError,
    DSLValidationError,
)


class TestDSLExceptions:
    """Test DSL exception classes."""

    def test_base_exception(self):
        """Test base DSL exception."""
        exc = DSLError("Test error")
        assert str(exc) == "Test error"
        assert isinstance(exc, Exception)

    def test_syntax_error_without_location(self):
        """Test syntax error without location info."""
        exc = DSLSyntaxError("Invalid syntax")
        assert str(exc) == "Syntax error: Invalid syntax"

    def test_syntax_error_with_line(self):
        """Test syntax error with line number."""
        exc = DSLSyntaxError("Invalid syntax", line=10)
        assert str(exc) == "Syntax error at line 10: Invalid syntax"

    def test_syntax_error_with_line_and_column(self):
        """Test syntax error with line and column."""
        exc = DSLSyntaxError("Invalid syntax", line=10, column=15)
        assert str(exc) == "Syntax error at line 10, column 15: Invalid syntax"
        assert exc.line == 10
        assert exc.column == 15

    def test_semantic_error(self):
        """Test semantic error."""
        exc = DSLSemanticError("Undefined reference")
        assert str(exc) == "Undefined reference"
        assert isinstance(exc, DSLError)

    def test_validation_error(self):
        """Test validation error."""
        exc = DSLValidationError("Invalid value")
        assert str(exc) == "Invalid value"
        assert isinstance(exc, DSLError)

    def test_exception_hierarchy(self):
        """Test exception hierarchy."""
        # All DSL exceptions should inherit from DSLError
        assert issubclass(DSLSyntaxError, DSLError)
        assert issubclass(DSLSemanticError, DSLError)
        assert issubclass(DSLValidationError, DSLError)

        # DSLError should inherit from Exception
        assert issubclass(DSLError, Exception)

    def test_exception_catching(self):
        """Test that exceptions can be caught properly."""
        # Can catch specific exception
        with pytest.raises(DSLSyntaxError):
            raise DSLSyntaxError("Test")

        # Can catch base exception
        with pytest.raises(DSLError):
            raise DSLSyntaxError("Test")

        # Can catch Exception
        with pytest.raises(Exception):
            raise DSLValidationError("Test")
