"""Tests for the render command."""

import struct

import pytest

pytest.importorskip("build123d")

from nichiyou_daiku.cli.dsl_cli import cli  # noqa: E402

CORNER = "(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n"


def _png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


@pytest.fixture
def corner(tmp_path):
    path = tmp_path / "corner.nd"
    path.write_text(CORNER)
    return path


def test_render_writes_a_png_next_to_the_input(runner, corner):
    result = runner.invoke(cli, ["render", str(corner)])
    assert result.exit_code == 0, result.output
    assert _png_size(corner.with_suffix(".png").read_bytes()) == (1400, 1400)


def test_render_takes_the_output_and_size(runner, corner, tmp_path):
    output = tmp_path / "check.png"
    result = runner.invoke(
        cli, ["render", str(corner), "-o", str(output), "--size", "600"]
    )
    assert result.exit_code == 0, result.output
    assert _png_size(output.read_bytes()) == (600, 600)


def test_render_warns_and_draws_when_pieces_are_not_connected(runner, tmp_path):
    loose = tmp_path / "loose.nd"
    loose.write_text("(a:2x4 =400)\n(b:2x4 =300)\n")
    result = runner.invoke(cli, ["render", str(loose)])
    assert result.exit_code == 0, result.output
    assert "not connected" in result.output
    assert loose.with_suffix(".png").exists()


def test_render_reads_stdin_with_output(runner, tmp_path):
    output = tmp_path / "from-stdin.png"
    result = runner.invoke(cli, ["render", "-", "-o", str(output)], input=CORNER)
    assert result.exit_code == 0, result.output
    assert _png_size(output.read_bytes()) == (1400, 1400)


def test_render_needs_an_output_for_stdin(runner):
    result = runner.invoke(cli, ["render", "-"], input=CORNER)
    assert result.exit_code == 1
    assert "-o" in result.output


def test_render_never_overwrites_the_input(runner, corner):
    result = runner.invoke(cli, ["render", str(corner), "-o", str(corner)])
    assert result.exit_code == 1
    assert corner.read_text() == CORNER


def test_render_rejects_a_tiny_size(runner, corner):
    result = runner.invoke(cli, ["render", str(corner), "--size", "100"])
    assert result.exit_code == 2


def test_render_reports_an_unwritable_output(runner, corner, tmp_path):
    output = tmp_path / "missing" / "check.png"
    result = runner.invoke(cli, ["render", str(corner), "-o", str(output)])
    assert result.exit_code == 1
    assert "Error rendering the image" in result.output
    assert "Traceback" not in result.output
