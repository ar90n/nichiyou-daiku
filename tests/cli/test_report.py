"""Tests for the report command."""

from nichiyou_daiku.cli.dsl_cli import cli


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


def test_report_missing_file_exits_1(runner, tmp_path):
    """Test report with a non-existent input file."""
    result = runner.invoke(cli, ["report", str(tmp_path / "missing.nd")])

    assert result.exit_code == 1
    assert "Error: File not found" in result.stderr


def test_report_output_path_is_directory(runner, tmp_path, simple_dsl):
    """Test report refuses to write to a directory."""
    dsl_file = tmp_path / "test.nd"
    dsl_file.write_text(simple_dsl)

    result = runner.invoke(cli, ["report", str(dsl_file), "-o", str(tmp_path)])

    assert result.exit_code == 1
    assert "Output path is not a file" in result.stderr


def test_report_verbose_keeps_stdout_clean(runner, tmp_path, simple_dsl):
    """Progress messages go to stderr so stdout is pure markdown."""
    dsl_file = tmp_path / "test.nd"
    dsl_file.write_text(simple_dsl)

    result = runner.invoke(cli, ["-v", "report", str(dsl_file)])

    assert result.exit_code == 0
    assert result.stdout.startswith("# Woodworking Project Report")
    assert "Parsing DSL file..." not in result.stdout
    assert "Parsing DSL file..." in result.stderr
    assert "Generating report..." in result.stderr


def test_report_status_message_goes_to_stderr(runner, tmp_path, simple_dsl):
    """The 'written to' notice is a status message, not output."""
    dsl_file = tmp_path / "test.nd"
    dsl_file.write_text(simple_dsl)
    output_file = tmp_path / "report.md"

    result = runner.invoke(cli, ["report", str(dsl_file), "-o", str(output_file)])

    assert result.exit_code == 0
    assert result.stdout == ""
    assert f"Report written to: {output_file}" in result.stderr


def test_report_quiet_suppresses_status(runner, tmp_path, simple_dsl):
    """Quiet mode prints nothing on success."""
    dsl_file = tmp_path / "test.nd"
    dsl_file.write_text(simple_dsl)
    output_file = tmp_path / "report.md"

    result = runner.invoke(
        cli, ["-q", "-v", "report", str(dsl_file), "-o", str(output_file)]
    )

    assert result.exit_code == 0
    assert result.output == ""


def test_report_kerf_option_changes_cut_allowance(runner, tmp_path):
    dsl_file = tmp_path / "pair.nd"
    dsl_file.write_text("(a:2x4 =1000)\n(b:2x4 =800)\na -[FL<100 DF<0]- b\n")

    default = runner.invoke(cli, ["report", str(dsl_file)])
    no_kerf = runner.invoke(cli, ["report", "--kerf", "0", str(dsl_file)])

    assert default.exit_code == 0 and no_kerf.exit_code == 0
    assert "Total waste: 634mm" in default.output  # two 3mm saw cuts
    assert "Total waste: 640mm" in no_kerf.output
