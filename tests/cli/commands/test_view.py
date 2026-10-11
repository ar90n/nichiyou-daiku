"""Tests for the view command."""

import sys
import types
from pathlib import Path

import pytest

from nichiyou_daiku.cli.commands import view as view_module
from nichiyou_daiku.cli.dsl_cli import cli

BEAM_DSL = "(beam:2x4 =1000)"


@pytest.fixture
def beam_file(tmp_path: Path) -> Path:
    dsl_file = tmp_path / "beam.nd"
    dsl_file.write_text(BEAM_DSL)
    return dsl_file


@pytest.fixture
def fillet_calls(monkeypatch) -> list[float]:
    """Skip the 3D conversion and record the requested fillet radius."""
    calls: list[float] = []

    def fake_convert(assembly, echo, fillet_radius=5.0):
        calls.append(fillet_radius)
        return object()

    monkeypatch.setattr(view_module, "convert_assembly_to_build123d", fake_convert)
    return calls


def install_fake_ocp_vscode(monkeypatch, show) -> None:
    fake = types.ModuleType("ocp_vscode")
    fake.show = show  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ocp_vscode", fake)


class TestViewCommand:
    def test_viewer_not_running_reports_error(
        self, runner, monkeypatch, beam_file, fillet_calls
    ):
        def show(_):
            raise RuntimeError("Cannot access viewer config")

        install_fake_ocp_vscode(monkeypatch, show)

        result = runner.invoke(cli, ["view", str(beam_file)])

        assert result.exit_code == 1
        assert isinstance(result.exception, SystemExit)
        assert "Cannot access viewer config" in result.stderr
        assert "Traceback" not in result.output

    def test_default_fillet_radius_matches_export(
        self, runner, monkeypatch, beam_file, fillet_calls
    ):
        install_fake_ocp_vscode(monkeypatch, lambda _: None)

        result = runner.invoke(cli, ["view", str(beam_file)])

        assert result.exit_code == 0, result.output
        assert fillet_calls == [5.0]

    def test_missing_file_exits_1(self, runner, tmp_path):
        result = runner.invoke(cli, ["view", str(tmp_path / "missing.nd")])

        assert result.exit_code == 1
        assert "Error: File not found" in result.stderr


def test_view_status_message_goes_to_stderr(
    runner, monkeypatch, beam_file, fillet_calls
):
    install_fake_ocp_vscode(monkeypatch, lambda _: None)

    result = runner.invoke(cli, ["view", str(beam_file)])

    assert result.exit_code == 0
    assert result.stdout == ""
    assert "Displaying in VS Code OCP CAD Viewer" in result.stderr


def test_view_debug_prints_viewer_traceback(
    runner, monkeypatch, beam_file, fillet_calls
):
    def show(_):
        raise RuntimeError("Cannot access viewer config")

    install_fake_ocp_vscode(monkeypatch, show)

    result = runner.invoke(cli, ["-d", "view", str(beam_file)])

    assert result.exit_code == 1
    assert "Traceback (most recent call last)" in result.stderr
