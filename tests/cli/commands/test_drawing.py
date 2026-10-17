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


def test_page_size_choices_match_the_drawing_module():
    pytest.importorskip("build123d")
    from nichiyou_daiku.cli.commands.drawing import drawing
    from nichiyou_daiku.shell.drawing import PAGE_SIZES

    # The CLI cannot import shell.drawing when it loads, so it lists the
    # page sizes itself
    option = next(param for param in drawing.params if param.name == "page_size")
    assert tuple(option.type.choices) == PAGE_SIZES  # type: ignore[attr-defined]


def test_drawing_explains_a_missing_cairo_library(runner, beam_file, monkeypatch):
    import nichiyou_daiku.cli.utils as utils

    def missing_cairo(name):
        # What cairocffi raises at import without the system library
        raise OSError('no library called "cairo-2" was found')

    monkeypatch.setattr(utils, "import_module", missing_cairo)
    result = runner.invoke(cli, ["drawing", str(beam_file)])
    assert result.exit_code == 1
    assert "the cairo library is missing" in result.output
    assert "brew install cairo" in result.output
    assert "Traceback" not in result.output


def _record_drawing_options(monkeypatch, *warn: Warning) -> dict:
    """Replace technical_drawing with one that records its options and
    raises the warnings ``warn``."""
    import warnings

    import nichiyou_daiku.shell.drawing as drawing_module

    real = drawing_module.technical_drawing
    options: dict = {}

    def recording(part, **kwargs):
        options.update(kwargs)
        for warning in warn:
            warnings.warn(warning)
        return real(part, **kwargs)

    monkeypatch.setattr(drawing_module, "technical_drawing", recording)
    return options


def test_drawing_has_dimensions_unless_asked_not_to(
    runner, tmp_path, beam_file, monkeypatch
):
    pytest.importorskip("build123d")
    options = _record_drawing_options(monkeypatch)
    output_file = tmp_path / "out.svg"

    result = runner.invoke(cli, ["drawing", str(beam_file), "-o", str(output_file)])
    assert result.exit_code == 0, result.output
    assert options["assembly"] is not None

    result = runner.invoke(
        cli, ["drawing", str(beam_file), "-o", str(output_file), "--no-dimensions"]
    )
    assert result.exit_code == 0, result.output
    assert options["assembly"] is None


def test_drawing_warns_about_crowded_dimensions(
    runner, tmp_path, beam_file, monkeypatch
):
    pytest.importorskip("build123d")
    from nichiyou_daiku.shell.dimensioning import CrowdedDimensionsWarning

    _record_drawing_options(
        monkeypatch,
        CrowdedDimensionsWarning("5 dimension values overlap"),
        UserWarning("a library has something to say"),
    )
    output_file = tmp_path / "out.svg"

    # Other warnings are passed on, not swallowed
    with pytest.warns(UserWarning, match="a library has something to say"):
        result = runner.invoke(cli, ["drawing", str(beam_file), "-o", str(output_file)])

    assert result.exit_code == 0, result.output
    assert "Warning: 5 dimension values overlap" in result.stderr
    assert output_file.exists()


def test_drawing_says_why_an_unconnected_design_has_no_dimensions(runner, tmp_path):
    pytest.importorskip("build123d")
    design = tmp_path / "two.nd"
    design.write_text("(a:2x4 =400)\n(b:2x4 =400)\n")
    output_file = tmp_path / "out.svg"

    result = runner.invoke(cli, ["drawing", str(design), "-o", str(output_file)])
    assert result.exit_code == 0, result.output
    assert "no dimensions" in result.stderr
    assert "2 separate parts" in result.stderr

    result = runner.invoke(
        cli, ["drawing", str(design), "-o", str(output_file), "--no-dimensions"]
    )
    assert "no dimensions" not in result.stderr


def test_drawing_keeps_the_warnings_given_before_a_failure(
    runner, tmp_path, beam_file, monkeypatch
):
    import warnings

    import nichiyou_daiku.shell.drawing as drawing_module
    from nichiyou_daiku.shell.dimensioning import CrowdedDimensionsWarning

    def failing(*args, **kwargs):
        warnings.warn(CrowdedDimensionsWarning("5 dimension values overlap"))
        raise RuntimeError("no projection")

    monkeypatch.setattr(drawing_module, "technical_drawing", failing)
    result = runner.invoke(
        cli, ["drawing", str(beam_file), "-o", str(tmp_path / "out.svg")]
    )
    assert result.exit_code == 1
    assert "Warning: 5 dimension values overlap" in result.stderr
    assert "Error creating drawing: no projection" in result.stderr
