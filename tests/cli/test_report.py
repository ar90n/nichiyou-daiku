"""Tests for the report command."""

from click.testing import CliRunner
import pytest

from nichiyou_daiku.cli.dsl_cli import cli


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def simple_dsl():
    """Simple DSL content for testing."""
    return """
(leg1:2x4 {"length": 720})
(leg2:2x4 {"length": 720})
(apron:1x4 {"length": 600})

leg1 -[{"contact_face": "front", "edge_shared_face": "right", "offset": FromMax(100)}
       {"contact_face": "left", "edge_shared_face": "bottom", "offset": FromMin(0)}]- apron
"""


def test_report_to_file(runner, tmp_path, simple_dsl):
    """Test generating report to file."""
    # Create temporary DSL file
    dsl_file = tmp_path / "test.nd"
    dsl_file.write_text(simple_dsl)

    # Output file
    output_file = tmp_path / "report.md"

    # Run command
    result = runner.invoke(
        cli,
        [
            "report",
            str(dsl_file),
            "-o",
            str(output_file),
            "--project-name",
            "Test Project",
        ],
    )

    assert result.exit_code == 0
    assert output_file.exists()

    # Check report content
    report_content = output_file.read_text()
    assert "# Test Project Report" in report_content
    assert "Bill of Materials" in report_content
    assert "Shopping List" in report_content


def test_report_to_stdout(runner, tmp_path, simple_dsl):
    """Test generating report to stdout."""
    # Create temporary DSL file
    dsl_file = tmp_path / "test.nd"
    dsl_file.write_text(simple_dsl)

    # Run command without output file
    result = runner.invoke(cli, ["report", str(dsl_file)])

    assert result.exit_code == 0
    assert "# Woodworking Project Report" in result.output
    assert "Bill of Materials" in result.output


def test_report_from_stdin(runner, simple_dsl):
    """Test generating report from stdin."""
    result = runner.invoke(
        cli, ["report", "-", "--project-name", "Stdin Test"], input=simple_dsl
    )

    assert result.exit_code == 0
    assert "# Stdin Test Report" in result.output


def test_report_no_cut_diagram(runner, tmp_path, simple_dsl):
    """Test generating report without cut diagram."""
    # Create temporary DSL file
    dsl_file = tmp_path / "test.nd"
    dsl_file.write_text(simple_dsl)

    # Run command
    result = runner.invoke(cli, ["report", str(dsl_file), "--no-cut-diagram"])

    assert result.exit_code == 0
    assert "Optimized Cut List" not in result.output


def test_report_verbose(runner, tmp_path, simple_dsl):
    """Test report with verbose output."""
    # Create temporary DSL file
    dsl_file = tmp_path / "test.nd"
    dsl_file.write_text(simple_dsl)

    # Run command with verbose
    result = runner.invoke(cli, ["-v", "report", str(dsl_file)])

    assert result.exit_code == 0
    assert "Parsing DSL file..." in result.output
    assert "Extracting resources..." in result.output
    assert "Generating report..." in result.output


def test_report_create_output_dir(runner, tmp_path, simple_dsl):
    """Test report creates output directory if needed."""
    # Create temporary DSL file
    dsl_file = tmp_path / "test.nd"
    dsl_file.write_text(simple_dsl)

    # Output file in non-existent directory
    output_file = tmp_path / "reports" / "nested" / "report.md"

    # Run command
    result = runner.invoke(cli, ["report", str(dsl_file), "-o", str(output_file)])

    assert result.exit_code == 0
    assert output_file.exists()
    assert output_file.parent.is_dir()
