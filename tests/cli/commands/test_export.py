"""Tests for DSL export command."""

import pytest
from click.testing import CliRunner
from pathlib import Path
import tempfile

from nichiyou_daiku.cli.dsl_cli import cli


class TestExportCommand:
    """Test export command functionality."""

    def test_export_command_exists(self):
        """Test that export command is available."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "export" in result.output

    def test_export_stl_format(self):
        """Test exporting to STL format."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test DSL file
            dsl_file = Path(tmpdir) / "test.nd"
            dsl_file.write_text("""
            // Simple table design
            (leg1:2x4 =720)
            (leg2:2x4 =720)
            (apron:2x4 =600)
            
            // Connections
            leg1 -[LB>0 DB>0]- apron
            leg2 -[RF>0 TF>0]- apron
            """)

            output_file = Path(tmpdir) / "output.stl"

            result = runner.invoke(
                cli, ["export", str(dsl_file), "-o", str(output_file), "-f", "stl"]
            )

            assert result.exit_code == 0
            assert output_file.exists()
            assert output_file.stat().st_size > 0

    def test_export_step_format(self):
        """Test exporting to STEP format."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test DSL file
            dsl_file = Path(tmpdir) / "test.nd"
            dsl_file.write_text("""
            (beam:2x4 =1000)
            """)

            output_file = Path(tmpdir) / "output.step"

            result = runner.invoke(
                cli, ["export", str(dsl_file), "-o", str(output_file), "-f", "step"]
            )

            assert result.exit_code == 0
            assert output_file.exists()
            assert output_file.stat().st_size > 0

    def test_export_auto_format_detection(self):
        """Test automatic format detection from output filename."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test DSL file
            dsl_file = Path(tmpdir) / "test.nd"
            dsl_file.write_text("""
            (beam:2x4 =1000)
            """)

            # Test STL auto-detection
            output_stl = Path(tmpdir) / "output.stl"
            result = runner.invoke(
                cli, ["export", str(dsl_file), "-o", str(output_stl)]
            )
            assert result.exit_code == 0
            assert output_stl.exists()

            # Test STEP auto-detection
            output_step = Path(tmpdir) / "output.step"
            result = runner.invoke(
                cli, ["export", str(dsl_file), "-o", str(output_step)]
            )
            assert result.exit_code == 0
            assert output_step.exists()

    def test_export_invalid_format(self):
        """Test export with invalid format."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            dsl_file = Path(tmpdir) / "test.nd"
            dsl_file.write_text("(beam:2x4 =1000)")

            result = runner.invoke(cli, ["export", str(dsl_file), "-f", "invalid"])

            assert result.exit_code != 0
            assert "Invalid value" in result.output or "is not one of" in result.output

    def test_export_invalid_dsl_file(self):
        """Test export with invalid DSL file."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            dsl_file = Path(tmpdir) / "invalid.nd"
            dsl_file.write_text("invalid dsl content")

            result = runner.invoke(cli, ["export", str(dsl_file), "-f", "stl"])

            assert result.exit_code != 0
            assert (
                "error" in result.output.lower() or "invalid" in result.output.lower()
            )

    def test_export_nonexistent_file(self):
        """Test export with non-existent file."""
        runner = CliRunner()
        result = runner.invoke(cli, ["export", "nonexistent.nd", "-f", "stl"])

        assert result.exit_code != 0
        assert (
            "not found" in result.output.lower()
            or "does not exist" in result.output.lower()
        )

    def test_export_fillet_radius_option(self):
        """Test export with custom fillet radius."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            dsl_file = Path(tmpdir) / "test.nd"
            dsl_file.write_text("(beam:2x4 =1000)")

            output_file = Path(tmpdir) / "output.stl"

            # Test with custom fillet radius
            result = runner.invoke(
                cli,
                [
                    "export",
                    str(dsl_file),
                    "-o",
                    str(output_file),
                    "-f",
                    "stl",
                    "--fillet-radius",
                    "10",
                ],
            )

            assert result.exit_code == 0
            assert output_file.exists()

            # Test with no fillet (radius=0)
            output_file2 = Path(tmpdir) / "output_no_fillet.stl"
            result = runner.invoke(
                cli,
                [
                    "export",
                    str(dsl_file),
                    "-o",
                    str(output_file2),
                    "-f",
                    "stl",
                    "--fillet-radius",
                    "0",
                ],
            )

            assert result.exit_code == 0
            assert output_file2.exists()

    def test_export_without_build123d(self):
        """Test export command when build123d is not available."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            dsl_file = Path(tmpdir) / "test.nd"
            dsl_file.write_text("(beam:2x4 =1000)")

            # Monkey patch to simulate missing build123d
            import nichiyou_daiku.shell.build123d_export as export_module

            original_has_build123d = export_module.HAS_BUILD123D

            try:
                export_module.HAS_BUILD123D = False

                result = runner.invoke(cli, ["export", str(dsl_file), "-f", "stl"])

                assert result.exit_code != 0
                assert "build123d" in result.output.lower()
                # The installed CLI lacks the extra; reinstall it with it
                assert (
                    'uv tool install --force "nichiyou-daiku[viz] @ '
                    'git+https://github.com/ar90n/nichiyou-daiku"' in result.output
                )
            finally:
                export_module.HAS_BUILD123D = original_has_build123d

    def test_export_default_output_filename(self):
        """Test export with default output filename."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create test file in current directory
            dsl_file = Path("furniture.nd")
            dsl_file.write_text("(beam:2x4 =1000)")

            result = runner.invoke(cli, ["export", "furniture.nd", "-f", "stl"])

            assert result.exit_code == 0
            # Should create furniture.stl in same directory
            expected_output = Path("furniture.stl")
            assert expected_output.exists()

    @pytest.mark.parametrize(
        "format,extension",
        [
            ("stl", ".stl"),
            ("step", ".step"),
            ("stp", ".stp"),
        ],
    )
    def test_export_format_aliases(self, format, extension):
        """Test export with various format aliases."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            dsl_file = Path(tmpdir) / "test.nd"
            dsl_file.write_text("(beam:2x4 =1000)")

            output_file = Path(tmpdir) / f"output{extension}"

            result = runner.invoke(
                cli, ["export", str(dsl_file), "-o", str(output_file), "-f", format]
            )

            # step/stp should be treated as same format
            if format in ["step", "stp"]:
                assert result.exit_code == 0
                assert output_file.exists()
            elif format == "stl":
                assert result.exit_code == 0
                assert output_file.exists()


BEAM_DSL = "(beam:2x4 =1000)"


@pytest.fixture
def beam_file(tmp_path: Path) -> Path:
    dsl_file = tmp_path / "beam.nd"
    dsl_file.write_text(BEAM_DSL)
    return dsl_file


class TestExportWriteFailures:
    """Export must not report success when nothing was written."""

    @pytest.mark.parametrize("fmt", ["stl", "step"])
    def test_missing_output_directory_fails(self, runner, tmp_path, beam_file, fmt):
        output_file = tmp_path / "no_such_dir" / f"out.{fmt}"

        result = runner.invoke(
            cli, ["export", str(beam_file), "-o", str(output_file), "-f", fmt]
        )

        assert result.exit_code == 1
        assert not output_file.exists()
        assert "Successfully exported" not in result.output
        assert "error" in result.stderr.lower()


class TestExportOutputSafety:
    """Export must not write mislabeled files or clobber its own input."""

    @pytest.mark.parametrize(
        "fmt,extension", [("stl", ".step"), ("stl", ".stp"), ("step", ".stl")]
    )
    def test_format_contradicting_output_extension_fails(
        self, runner, tmp_path, beam_file, fmt, extension
    ):
        output_file = tmp_path / f"out{extension}"

        result = runner.invoke(
            cli, ["export", str(beam_file), "-o", str(output_file), "-f", fmt]
        )

        assert result.exit_code == 1
        assert not output_file.exists()
        assert extension in result.stderr

    @pytest.mark.parametrize("fmt,extension", [("step", ".stp"), ("stp", ".step")])
    def test_step_aliases_are_compatible(
        self, runner, tmp_path, beam_file, fmt, extension
    ):
        output_file = tmp_path / f"out{extension}"

        result = runner.invoke(
            cli, ["export", str(beam_file), "-o", str(output_file), "-f", fmt]
        )

        assert result.exit_code == 0
        assert output_file.exists()

    def test_unknown_output_extension_with_explicit_format_is_allowed(
        self, runner, tmp_path, beam_file
    ):
        output_file = tmp_path / "out.mesh"

        result = runner.invoke(
            cli, ["export", str(beam_file), "-o", str(output_file), "-f", "stl"]
        )

        assert result.exit_code == 0
        assert output_file.exists()

    def test_derived_output_never_overwrites_input(self, runner, tmp_path):
        dsl_file = tmp_path / "design.step"
        dsl_file.write_text(BEAM_DSL)

        result = runner.invoke(cli, ["export", str(dsl_file), "-f", "step"])

        assert result.exit_code == 1
        assert dsl_file.read_text() == BEAM_DSL
        assert "input" in result.stderr.lower()

    def test_explicit_output_never_overwrites_input(self, runner, tmp_path):
        dsl_file = tmp_path / "design.stl"
        dsl_file.write_text(BEAM_DSL)

        result = runner.invoke(cli, ["export", str(dsl_file), "-o", str(dsl_file)])

        assert result.exit_code == 1
        assert dsl_file.read_text() == BEAM_DSL
        assert "input" in result.stderr.lower()


class TestExportInputHandling:
    """Export accepts '-' for stdin and exits 1 on a missing file."""

    def test_reads_from_stdin_with_output(self, runner, tmp_path):
        output_file = tmp_path / "out.stl"

        result = runner.invoke(
            cli, ["export", "-", "-o", str(output_file)], input=BEAM_DSL
        )

        assert result.exit_code == 0, result.output
        assert output_file.exists()

    def test_stdin_requires_output(self, runner, tmp_path):
        result = runner.invoke(cli, ["export", "-", "-f", "stl"], input=BEAM_DSL)

        assert result.exit_code == 1
        assert "stdin" in result.stderr
        assert "-o" in result.stderr

    def test_missing_input_file_exits_1(self, runner, tmp_path):
        missing = tmp_path / "missing.nd"

        result = runner.invoke(cli, ["export", str(missing), "-f", "stl"])

        assert result.exit_code == 1
        assert "File not found" in result.stderr


def test_export_status_message_goes_to_stderr(runner, tmp_path, beam_file):
    output_file = tmp_path / "out.stl"

    result = runner.invoke(
        cli, ["-v", "export", str(beam_file), "-o", str(output_file)]
    )

    assert result.exit_code == 0
    assert result.stdout == ""
    assert "Successfully exported to" in result.stderr
    assert "Parsing DSL file..." in result.stderr
