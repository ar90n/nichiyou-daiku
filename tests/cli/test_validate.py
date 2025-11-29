"""Tests for the validate command."""

from nichiyou_daiku.cli.dsl_cli import cli


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
