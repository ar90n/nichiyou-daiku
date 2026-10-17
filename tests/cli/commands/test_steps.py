"""Tests for the steps command."""

import struct

import pytest

pytest.importorskip("build123d")

from nichiyou_daiku.cli.dsl_cli import cli  # noqa: E402

CORNER = "(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n"
CORNER_STEPS = CORNER + 'steps {\n  "Corner": a, b\n}\n'
# The corner joined with dowels: both pieces drilled, each its own part
DOWELLED = CORNER.replace("BD<0]", "BD<0 D(:8x30)]")
# A third piece across the far end of b: two steps without a steps block
THREE = CORNER + "(c:2x4 =400)\nb -[TF<0 BD<0]- c\n"


def _png_width(data: bytes) -> int:
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">I", data[16:20])[0]


@pytest.fixture
def corner(tmp_path):
    path = tmp_path / "corner.nd"
    path.write_text(CORNER_STEPS)
    return path


def test_steps_writes_the_page_and_images_next_to_the_input(runner, corner):
    result = runner.invoke(cli, ["steps", str(corner)])
    assert result.exit_code == 0, result.output
    directory = corner.with_name("corner-steps")
    assert sorted(p.name for p in directory.iterdir()) == ["step-01.png", "steps.md"]
    assert (directory / "steps.md").read_text().startswith("# corner: assembly steps\n")
    assert _png_width((directory / "step-01.png").read_bytes()) == 1600
    assert "Successfully wrote steps.md and 1 step image to" in result.stderr
    assert result.stdout == ""


def test_steps_draws_the_drilled_parts(runner, tmp_path):
    path = tmp_path / "corner.nd"
    path.write_text(DOWELLED)
    result = runner.invoke(cli, ["steps", str(path)])
    assert result.exit_code == 0, result.output
    directory = tmp_path / "corner-steps"
    assert sorted(p.name for p in directory.iterdir()) == [
        "part-01.png",
        "part-02.png",
        "step-01.png",
        "steps.md",
    ]
    assert _png_width((directory / "part-01.png").read_bytes()) == 1600
    assert (
        "Successfully wrote steps.md, 2 part drawings and 1 step image to"
        in result.stderr
    )


def test_steps_takes_a_directory_and_an_image_width(runner, corner, tmp_path):
    out = tmp_path / "instructions"
    result = runner.invoke(cli, ["steps", str(corner), "-o", str(out), "--size", "800"])
    assert result.exit_code == 0, result.output
    assert _png_width((out / "step-01.png").read_bytes()) == 800


def test_steps_without_a_steps_block_says_how_to_group(runner, tmp_path):
    path = tmp_path / "three.nd"
    path.write_text(THREE)
    result = runner.invoke(cli, ["steps", str(path)])
    assert result.exit_code == 0, result.output
    assert "No steps block: each step adds one piece" in result.stderr
    # A hint, not a warning
    assert "Warning" not in result.stderr


def test_steps_hint_names_the_designs_own_pieces(runner, tmp_path):
    path = tmp_path / "three.nd"
    path.write_text(THREE)
    result = runner.invoke(cli, ["steps", str(path)])
    assert result.exit_code == 0, result.output
    assert 'steps { "Frame": a, b, ... }' in result.stderr


def test_a_single_step_gets_no_hint(runner, tmp_path):
    path = tmp_path / "corner.nd"
    path.write_text(CORNER)
    result = runner.invoke(cli, ["steps", str(path)])
    assert result.exit_code == 0, result.output
    assert "No steps block" not in result.stderr


def test_steps_refuses_a_file_as_the_directory(runner, corner, tmp_path):
    taken = tmp_path / "taken.txt"
    taken.write_text("keep me")
    result = runner.invoke(cli, ["steps", str(corner), "-o", str(taken)])
    assert result.exit_code == 1
    assert "is a file" in result.stderr
    assert taken.read_text() == "keep me"


def test_steps_from_stdin_needs_a_directory(runner):
    result = runner.invoke(cli, ["steps", "-"], input=CORNER)
    assert result.exit_code == 1
    assert "-o" in result.stderr


def test_steps_reports_a_wrong_steps_block(runner, tmp_path):
    path = tmp_path / "corner.nd"
    path.write_text(CORNER + 'steps {\n  "Corner": a\n}\n')
    result = runner.invoke(cli, ["steps", str(path)])
    assert result.exit_code == 1
    assert "steps leaves out b" in result.stderr


def test_steps_without_the_viz_extra_says_how_to_install_it(
    runner, corner, monkeypatch
):
    import nichiyou_daiku.shell.build123d_export as export_module

    monkeypatch.setattr(export_module, "HAS_BUILD123D", False)
    result = runner.invoke(cli, ["steps", str(corner)])
    assert result.exit_code == 1
    assert "build123d is required" in result.stderr
    assert 'uv tool install --force "nichiyou-daiku[viz] @ ' in result.stderr
    assert not corner.with_name("corner-steps").exists()
