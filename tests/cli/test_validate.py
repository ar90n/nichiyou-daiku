"""Tests for the validate command."""

from click.testing import CliRunner
import pytest

from nichiyou_daiku.cli.dsl_cli import cli


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def valid_dsl():
    """Valid DSL content."""
    return """
(piece1:2x4 {"length": 1000})
(piece2:1x4 {"length": 800})

piece1 -[{"contact_face": "top", "edge_shared_face": "front", "offset": FromMin(0)}
         {"contact_face": "down", "edge_shared_face": "left", "offset": FromMax(100)}]- piece2
"""


@pytest.fixture
def invalid_syntax_dsl():
    """DSL with syntax error."""
    return """
(piece1:INVALID_TYPE {"length": 1000})
"""


@pytest.fixture
def invalid_semantic_dsl():
    """DSL with semantic error."""
    return """
(piece1:2x4 {"length": 1000})

piece1 -[{"contact_face": "top", "edge_shared_face": "front", "offset": FromMin(0)}
         {"contact_face": "down", "edge_shared_face": "left", "offset": FromMax(100)}]- unknown_piece
"""


def test_validate_valid_file(runner, tmp_path, valid_dsl):
    """Test validating a valid .nd file."""
    # Create temporary file
    dsl_file = tmp_path / "test.nd"
    dsl_file.write_text(valid_dsl)

    # Run command
    result = runner.invoke(cli, ["validate", str(dsl_file)])

    assert result.exit_code == 0
    assert "✓ DSL syntax is valid" in result.output


def test_validate_verbose(runner, tmp_path, valid_dsl):
    """Test validate with verbose output."""
    # Create temporary file
    dsl_file = tmp_path / "test.nd"
    dsl_file.write_text(valid_dsl)

    # Run command with verbose
    result = runner.invoke(cli, ["-v", "validate", str(dsl_file)])

    assert result.exit_code == 0
    assert "Model summary:" in result.output
    assert "Pieces: 2" in result.output
    assert "Connections: 1" in result.output
    assert "piece1: 2x4 @ 1000.0mm" in result.output


def test_validate_quiet(runner, tmp_path, valid_dsl):
    """Test validate with quiet mode."""
    # Create temporary file
    dsl_file = tmp_path / "test.nd"
    dsl_file.write_text(valid_dsl)

    # Run command with quiet
    result = runner.invoke(cli, ["-q", "validate", str(dsl_file)])

    assert result.exit_code == 0
    assert result.output == ""


def test_validate_stdin(runner, valid_dsl):
    """Test validating from stdin."""
    result = runner.invoke(cli, ["validate", "-"], input=valid_dsl)

    assert result.exit_code == 0
    assert "✓ DSL syntax is valid" in result.output


def test_validate_syntax_error(runner, tmp_path, invalid_syntax_dsl):
    """Test validating file with syntax error."""
    # Create temporary file
    dsl_file = tmp_path / "test.nd"
    dsl_file.write_text(invalid_syntax_dsl)

    # Run command
    result = runner.invoke(cli, ["validate", str(dsl_file)])

    assert result.exit_code == 1
    assert "✗ Syntax error" in result.output


def test_validate_semantic_error(runner, tmp_path, invalid_semantic_dsl):
    """Test validating file with semantic error."""
    # Create temporary file
    dsl_file = tmp_path / "test.nd"
    dsl_file.write_text(invalid_semantic_dsl)

    # Run command
    result = runner.invoke(cli, ["validate", str(dsl_file)])

    assert result.exit_code == 1
    assert "✗ Semantic error" in result.output
    assert "unknown_piece" in result.output


def test_validate_missing_file(runner):
    """Test validating non-existent file."""
    result = runner.invoke(cli, ["validate", "nonexistent.nd"])

    assert result.exit_code == 1
    assert "File not found" in result.output
