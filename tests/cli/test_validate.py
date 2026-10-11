"""Tests for the validate command."""

import pytest

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


def _validate(runner, tmp_path, dsl, *args):
    dsl_file = tmp_path / "design.nd"
    dsl_file.write_text(dsl)
    return runner.invoke(cli, ["validate", *args, str(dsl_file)])


def test_validate_reports_model_is_valid(runner, tmp_path, valid_dsl):
    result = _validate(runner, tmp_path, valid_dsl)
    assert result.exit_code == 0
    assert "✓ Model is valid" in result.output


def test_validate_reports_assembly_errors(runner, tmp_path):
    # The dowel layout does not support this face/edge combination yet
    result = _validate(
        runner,
        tmp_path,
        """
        (a:2x4 =500)
        (b:2x4 =500)
        a -[FL<100 BL<100 D(4, 30)]- b
        """,
    )
    assert result.exit_code == 1
    assert "✗ Assembly error" in result.output


def test_validate_reports_dowels_outside_the_piece(runner, tmp_path):
    result = _validate(
        runner,
        tmp_path,
        """
        (base:2x4 =500)
        (target:2x4 =300)
        base -[LT<19 DF<44.5 D(4, 30)]- target
        """,
    )
    assert result.exit_code == 1
    assert "outside" in result.output
    assert "base" in result.output


def test_validate_reports_overlapping_pieces(runner, tmp_path):
    result = _validate(
        runner,
        tmp_path,
        """
        (a:2x4 =500)
        (b:2x4 =300)
        (c:2x4 =300)
        a -[FL<100 DF<0]- b
        a -[FL<100 DF<0]- c
        """,
    )
    assert result.exit_code == 1
    assert "overlap" in result.output
    assert "b" in result.output and "c" in result.output


def test_validate_reports_contradicting_connections(runner, tmp_path):
    result = _validate(
        runner,
        tmp_path,
        """
        (a:2x4 =500)
        (b:2x4 =300)
        (c:2x4 =300)
        a -[FL<100 DF<0]- b
        a -[FL>100 DF<0]- c
        b -[RF<0 LF<0]- c
        """,
    )
    assert result.exit_code == 1
    assert (
        "Connection b -> c: contact (z) is off by 389.0mm (loop: b -> a -> c)"
        in result.output
    )


def test_validate_rejects_unconnected_pieces(runner, tmp_path):
    result = _validate(
        runner,
        tmp_path,
        """
        (a:2x4 =500)
        (b:2x4 =300)
        (floating:2x4 =300)
        a -[FL<100 DF<0]- b
        """,
    )
    assert result.exit_code == 1
    assert "not connected" in result.output
    assert "floating" in result.output
    # Unconnected groups have no relative position, so they are not
    # reported as overlapping each other
    assert "overlap" not in result.output


def test_validate_debug_prints_traceback_for_assembly_errors(runner, tmp_path):
    dsl_file = tmp_path / "design.nd"
    dsl_file.write_text("(a:2x4 =500)\n(b:2x4 =500)\na -[FL<100 BL<100 D(4, 30)]- b\n")
    result = runner.invoke(cli, ["-d", "validate", str(dsl_file)])
    assert result.exit_code == 1
    assert "Traceback" in result.output


def test_validate_does_not_need_build123d(runner, tmp_path, monkeypatch):
    import nichiyou_daiku.shell.build123d_export as export_module

    monkeypatch.setattr(export_module, "HAS_BUILD123D", False)
    result = _validate(
        runner,
        tmp_path,
        """
        (a:2x4 =500)
        (b:2x4 =300)
        (c:2x4 =300)
        a -[FL<100 DF<0]- b
        a -[FL<100 DF<0]- c
        """,
    )
    assert result.exit_code == 1
    assert "Pieces 'b' and 'c' overlap (1014600.0mm³)" in result.output


def test_validate_reports_orientation_conflicts(runner, tmp_path):
    result = _validate(
        runner,
        tmp_path,
        """
        (a:2x4 =500)
        (b:2x4 =300)
        (c:2x4 =300)
        a -[RF<0 LF<0]- b
        a -[FL<100 DF<0]- c
        b -[RF<0 LF<0]- c
        """,
    )
    assert result.exit_code == 1
    assert (
        "Connection b -> c: orientation contradicts the other connections (loop: b -> a -> c)"
        in result.output
    )
