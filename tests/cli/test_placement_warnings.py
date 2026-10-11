"""Commands other than validate warn about placement issues and carry on."""

import pytest

from nichiyou_daiku.cli.dsl_cli import cli
from nichiyou_daiku.shell.build123d_export import HAS_BUILD123D

CONTRADICTING = """
(a:2x4 =500)
(b:2x4 =300)
(c:2x4 =300)
a -[FL<100 DF<0]- b
a -[FL>100 DF<0]- c
b -[RF<0 LF<0]- c
"""


def _write(tmp_path, source: str):
    path = tmp_path / "design.nd"
    path.write_text(source)
    return path


def test_report_warns_and_continues(runner, tmp_path):
    result = runner.invoke(cli, ["report", str(_write(tmp_path, CONTRADICTING))])
    assert result.exit_code == 0
    assert "Warning: Connection b -> c: contact (z) is off by 389.0mm" in result.output
    assert "## Bill of Materials" in result.output


def test_report_warns_about_unconnected_pieces(runner, tmp_path):
    source = "(a:2x4 =500)\n(b:2x4 =300)\n(spare:2x4 =300)\na -[FL<100 DF<0]- b\n"
    result = runner.invoke(cli, ["report", str(_write(tmp_path, source))])
    assert result.exit_code == 0
    assert "Warning: Some pieces are not connected" in result.output


@pytest.mark.skipif(not HAS_BUILD123D, reason="export needs build123d")
def test_export_warns_and_continues(runner, tmp_path):
    output = tmp_path / "design.step"
    result = runner.invoke(
        cli,
        [
            "export",
            str(_write(tmp_path, CONTRADICTING)),
            "-f",
            "step",
            "-o",
            str(output),
        ],
    )
    assert result.exit_code == 0
    assert "Warning: Connection b -> c" in result.output
    assert output.exists()


def test_report_shows_overall_size(runner, tmp_path):
    source = "(a:2x4 =500)\n(b:2x4 =300)\na -[FL<100 DF<0]- b\n"
    result = runner.invoke(cli, ["report", str(_write(tmp_path, source))])
    assert result.exit_code == 0
    assert (
        "- **Overall Size (X × Y × Z)**: 89 × 338 × 500 mm "
        "(Z is the length direction of 'a')" in result.output
    )


def test_report_warns_about_fasteners_that_do_not_fit(runner, tmp_path):
    source = "(a:2x4 =500)\n(b:1x4 =300)\na -[FL<100 DF<0 D(5, 30)]- b\n"
    result = runner.invoke(cli, ["report", str(_write(tmp_path, source))])
    assert result.exit_code == 0
    assert (
        "Warning: Connection a -> b: contact area 19.0 x 89.0mm is too narrow"
        in result.output
    )
