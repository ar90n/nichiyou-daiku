"""Tests for --debug tracebacks and CLI logging configuration."""

import logging

import pytest

import nichiyou_daiku.dsl
from nichiyou_daiku.cli.commands import drawing as drawing_module
from nichiyou_daiku.cli.commands import report as report_module
from nichiyou_daiku.cli.dsl_cli import cli
from nichiyou_daiku.core.assembly import Assembly

BEAM_DSL = "(beam:2x4 =1000)"


def _boom(*args, **kwargs):
    raise RuntimeError("boom")


def _patch_parse(monkeypatch):
    monkeypatch.setattr(nichiyou_daiku.dsl, "parse_dsl", _boom)


def _patch_assembly(monkeypatch):
    monkeypatch.setattr(Assembly, "of", _boom)


def _patch_extract_resources(monkeypatch):
    monkeypatch.setattr(report_module, "extract_resources", _boom)


def _patch_export_stl(monkeypatch):
    import build123d

    monkeypatch.setattr(build123d, "export_stl", _boom)


def _patch_projection(monkeypatch):
    monkeypatch.setattr(drawing_module, "project_to_2d", _boom)


UNEXPECTED_FAILURES = [
    pytest.param(_patch_parse, ["report"], id="parse"),
    pytest.param(_patch_assembly, ["report"], id="assembly"),
    pytest.param(_patch_extract_resources, ["report"], id="report-resources"),
    pytest.param(_patch_export_stl, ["export", "-f", "stl"], id="export-write"),
    pytest.param(_patch_projection, ["drawing"], id="drawing-projection"),
]


@pytest.fixture
def beam_file(tmp_path):
    dsl_file = tmp_path / "beam.nd"
    dsl_file.write_text(BEAM_DSL)
    return dsl_file


@pytest.mark.parametrize("patch,command", UNEXPECTED_FAILURES)
def test_debug_prints_traceback_for_unexpected_errors(
    runner, monkeypatch, beam_file, patch, command
):
    patch(monkeypatch)

    result = runner.invoke(cli, ["-d", *command, str(beam_file)])

    assert result.exit_code == 1
    assert "boom" in result.stderr
    assert "Traceback (most recent call last)" in result.stderr


@pytest.mark.parametrize("patch,command", UNEXPECTED_FAILURES)
def test_no_traceback_without_debug(runner, monkeypatch, beam_file, patch, command):
    patch(monkeypatch)

    result = runner.invoke(cli, [*command, str(beam_file)])

    assert result.exit_code == 1
    assert "boom" in result.stderr
    assert "Traceback" not in result.output


def simulate_fresh_process_logging(monkeypatch):
    """Reset logging to a fresh-process state: no root handlers, default levels.

    Called inside the test body because pytest attaches its capture handlers
    to the root logger at the start of the call phase, which would make
    logging.basicConfig a no-op and hide root-level configuration.
    """
    root = logging.getLogger()
    package_logger = logging.getLogger("nichiyou_daiku")
    monkeypatch.setattr(root, "handlers", [])
    monkeypatch.setattr(root, "level", logging.WARNING)
    monkeypatch.setattr(package_logger, "handlers", [])
    monkeypatch.setattr(package_logger, "level", logging.NOTSET)


def test_verbose_does_not_enable_third_party_info_logs(runner, monkeypatch, beam_file):
    simulate_fresh_process_logging(monkeypatch)

    result = runner.invoke(cli, ["-v", "report", str(beam_file)])

    assert result.exit_code == 0
    assert logging.getLogger().handlers == []
    assert logging.getLogger("build123d").getEffectiveLevel() > logging.INFO
    assert logging.getLogger("nichiyou_daiku").getEffectiveLevel() == logging.INFO


def test_debug_enables_package_debug_logs_only(runner, monkeypatch, beam_file):
    simulate_fresh_process_logging(monkeypatch)

    result = runner.invoke(cli, ["-d", "report", str(beam_file)])

    assert result.exit_code == 0
    assert logging.getLogger("build123d").getEffectiveLevel() > logging.DEBUG
    assert logging.getLogger("nichiyou_daiku").getEffectiveLevel() == logging.DEBUG


def test_package_logs_reach_stderr(runner, monkeypatch, beam_file):
    real_extract = report_module.extract_resources

    def logging_extract(assembly):
        logging.getLogger("nichiyou_daiku.shell").info("hello from the library")
        return real_extract(assembly)

    monkeypatch.setattr(report_module, "extract_resources", logging_extract)
    simulate_fresh_process_logging(monkeypatch)

    result = runner.invoke(cli, ["-v", "report", str(beam_file)])

    assert result.exit_code == 0
    assert "hello from the library" in result.stderr
    assert "hello from the library" not in result.stdout
