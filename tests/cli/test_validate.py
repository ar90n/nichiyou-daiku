"""Tests for the validate command."""

import subprocess
import sys

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


def test_validate_accepts_dowels_on_formerly_unsupported_faces(runner, tmp_path):
    # front/back to front/back with left edges used to fail with NotImplementedError
    result = _validate(
        runner,
        tmp_path,
        """
        (a:2x4 =500)
        (b:2x4 =500)
        a -[FL<100 BL<100 D(4, 30)]- b
        """,
    )
    assert result.exit_code == 0
    assert "✓ Model is valid" in result.output


def test_validate_reports_fasteners_that_do_not_fit(runner, tmp_path):
    result = _validate(
        runner,
        tmp_path,
        """
        (a:2x4 =500)
        (b:1x4 =300)
        a -[FL<100 DF<0 D(5, 30)]- b
        """,
    )
    assert result.exit_code == 1
    assert (
        "Connection a -> b: contact area 19.0 x 89.0mm is too narrow for a 10.0mm dowel"
        in result.output
    )


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
        "Connection b -> c: contact (z) is off by 389mm (loop: b -> a -> c)"
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


def test_validate_debug_prints_traceback_for_assembly_errors(
    runner, tmp_path, monkeypatch
):
    import nichiyou_daiku.cli.commands.validate as validate_module

    def broken(model):
        raise RuntimeError("boom")

    monkeypatch.setattr(validate_module.Assembly, "of", broken)
    dsl_file = tmp_path / "design.nd"
    dsl_file.write_text("(a:2x4 =500)\n(b:2x4 =300)\na -[FL<100 DF<0]- b\n")
    result = runner.invoke(cli, ["-d", "validate", str(dsl_file)])
    assert result.exit_code == 1
    assert "✗ Assembly error" in result.output
    assert "Traceback" in result.output


def test_validate_does_not_need_build123d(tmp_path):
    # Run in a fresh interpreter where importing build123d fails
    design = tmp_path / "design.nd"
    design.write_text(
        "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\n"
        "a -[FL<100 DF<0]- b\na -[FL<100 DF<0]- c\n"
    )
    script = (
        "import sys\n"
        "sys.modules['build123d'] = None\n"
        "from nichiyou_daiku.cli.dsl_cli import cli\n"
        f"cli(['validate', {str(design)!r}])\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "Pieces 'b' and 'c' overlap (1014600mm³)" in result.stdout + result.stderr


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


def test_validate_shows_small_mismatches_without_rounding_them_to_zero(
    runner, tmp_path
):
    from pathlib import Path

    table = (
        Path(__file__).parents[2] / "examples" / "nd_files" / "simple_table_compact.nd"
    ).read_text()
    source = table.replace(
        "leg_4 -[FL<100 TF<0]- apron_right", "leg_4 -[FL<100.01 TF<0]- apron_right"
    )
    result = _validate(runner, tmp_path, source)
    assert result.exit_code == 1
    assert "edge (z) is off by 0.01mm" in result.output


def test_format_mm_keeps_small_values_visible():
    from nichiyou_daiku.shell.report_generator import format_mm

    assert format_mm(389.0) == "389"
    assert format_mm(-89.25) == "-89.2"
    assert format_mm(0.01) == "0.01"
    assert format_mm(0.00042) == "0.00042"
