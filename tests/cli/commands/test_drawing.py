"""Tests for the drawing command."""

from pathlib import Path

import pytest

from nichiyou_daiku.cli.dsl_cli import cli

BEAM_DSL = "(beam:2x4 =1000)"


@pytest.fixture
def beam_file(tmp_path: Path) -> Path:
    dsl_file = tmp_path / "beam.nd"
    dsl_file.write_text(BEAM_DSL)
    return dsl_file


class TestDrawingInputHandling:
    """Drawing accepts '-' for stdin and exits 1 on a missing file."""

    def test_reads_from_stdin_with_output(self, runner, tmp_path):
        output_file = tmp_path / "out.pdf"

        result = runner.invoke(
            cli, ["drawing", "-", "-o", str(output_file)], input=BEAM_DSL
        )

        assert result.exit_code == 0, result.output
        assert output_file.read_bytes().startswith(b"%PDF")

    def test_stdin_requires_output(self, runner):
        result = runner.invoke(cli, ["drawing", "-"], input=BEAM_DSL)

        assert result.exit_code == 1
        assert "stdin" in result.stderr
        assert "-o" in result.stderr

    def test_missing_input_file_exits_1(self, runner, tmp_path):
        missing = tmp_path / "missing.nd"

        result = runner.invoke(cli, ["drawing", str(missing)])

        assert result.exit_code == 1
        assert "File not found" in result.stderr


class TestDrawingOutputFiles:
    """Drawing writes exactly the requested file and nothing else."""

    def test_svg_output_is_kept(self, runner, tmp_path, beam_file):
        output_file = tmp_path / "out.svg"

        result = runner.invoke(cli, ["drawing", str(beam_file), "-o", str(output_file)])

        assert result.exit_code == 0, result.output
        assert output_file.exists()
        assert "<svg" in output_file.read_text()

    def test_pdf_output_preserves_existing_svg_sibling(
        self, runner, tmp_path, beam_file
    ):
        existing_svg = tmp_path / "keep.svg"
        existing_svg.write_text("user content")
        output_file = tmp_path / "keep.pdf"

        result = runner.invoke(cli, ["drawing", str(beam_file), "-o", str(output_file)])

        assert result.exit_code == 0, result.output
        assert output_file.read_bytes().startswith(b"%PDF")
        assert existing_svg.read_text() == "user content"

    def test_pdf_output_leaves_no_temporary_files(self, runner, tmp_path, beam_file):
        result = runner.invoke(cli, ["drawing", str(beam_file)])

        assert result.exit_code == 0, result.output
        assert sorted(p.name for p in tmp_path.iterdir()) == ["beam.nd", "beam.pdf"]

    def test_never_overwrites_input(self, runner, tmp_path):
        dsl_file = tmp_path / "design.pdf"
        dsl_file.write_text(BEAM_DSL)

        result = runner.invoke(cli, ["drawing", str(dsl_file)])

        assert result.exit_code == 1
        assert dsl_file.read_text() == BEAM_DSL
        assert "input" in result.stderr.lower()


def test_drawing_status_message_goes_to_stderr(runner, tmp_path, beam_file):
    output_file = tmp_path / "out.svg"

    result = runner.invoke(cli, ["drawing", str(beam_file), "-o", str(output_file)])

    assert result.exit_code == 0
    assert result.stdout == ""
    assert "Successfully created technical drawing" in result.stderr


def test_drawing_failure_is_reported(runner, tmp_path, beam_file, monkeypatch):
    import nichiyou_daiku.shell.drawing as drawing_module

    def broken(*args, **kwargs):
        raise RuntimeError("no projection")

    monkeypatch.setattr(drawing_module, "technical_drawing", broken)
    result = runner.invoke(
        cli, ["drawing", str(beam_file), "-o", str(tmp_path / "out.svg")]
    )
    assert result.exit_code == 1
    assert "Error creating drawing: no projection" in result.output
