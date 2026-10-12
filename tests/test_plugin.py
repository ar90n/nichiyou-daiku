"""The Claude Code plugin: manifests, skills and the CLI wrapper."""

import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def _json(name: str) -> dict:
    return json.loads((ROOT / ".claude-plugin" / name).read_text())


def test_plugin_manifest_names_the_plugin():
    manifest = _json("plugin.json")
    assert manifest["name"] == "nichiyou-daiku"
    assert manifest["description"]
    # A version pins users to it; without one they follow the commits
    assert "version" not in manifest


def test_marketplace_offers_the_repository_as_the_plugin():
    marketplace = _json("marketplace.json")
    assert marketplace["name"] == "nichiyou-daiku"
    assert marketplace["owner"]["name"]
    [entry] = marketplace["plugins"]
    assert entry["name"] == _json("plugin.json")["name"]
    assert entry["source"] == "./"


WRAPPER = ROOT / "bin" / "nichiyou-daiku"


def _tools(tmp_path: Path) -> Path:
    """Only the utilities the wrapper needs, so a uv or nichiyou-daiku
    installed on this machine stays out of the tests."""
    tools = tmp_path / "tools"
    tools.mkdir(exist_ok=True)
    for name in ("dirname", "basename", "readlink"):
        if not (tools / name).exists():
            (tools / name).symlink_to(shutil.which(name))
    return tools


def _fake(directory: Path, name: str, label: str) -> None:
    """An executable that prints its label, then each argument on a line."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(f'#!/bin/sh\necho {label}\nfor arg in "$@"; do echo "$arg"; done\n')
    path.chmod(0o755)


def _plugin(tmp_path: Path, name: str = "plugin") -> Path:
    """A plugin root holding a copy of the wrapper."""
    bin_dir = tmp_path / name / "bin"
    bin_dir.mkdir(parents=True)
    shutil.copy2(WRAPPER, bin_dir / "nichiyou-daiku")
    return (tmp_path / name).resolve()


def _run(
    command: Path,
    *path: Path | str,
    args=("validate", "my table.nd"),
    env=None,
    cwd=None,
):
    return subprocess.run(
        [str(command), *args],
        env={"PATH": os.pathsep.join(str(p) for p in path), **(env or {})},
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_wrapper_is_an_executable_posix_shell_script():
    assert WRAPPER.read_text().startswith("#!/bin/sh\n")
    assert WRAPPER.stat().st_mode & stat.S_IXUSR
    assert subprocess.run(["sh", "-n", str(WRAPPER)]).returncode == 0


@pytest.mark.parametrize("installed_first", [True, False])
def test_wrapper_runs_an_installed_cli(tmp_path, installed_first):
    root = _plugin(tmp_path)
    _fake(tmp_path / "installed", "nichiyou-daiku", "installed")
    _fake(tmp_path / "uv-bin", "uv", "uv")
    dirs = [tmp_path / "installed", root / "bin"]
    if not installed_first:
        dirs.reverse()
    result = _run(
        root / "bin" / "nichiyou-daiku", *dirs, tmp_path / "uv-bin", _tools(tmp_path)
    )
    assert result.stdout.splitlines() == ["installed", "validate", "my table.nd"]


def test_wrapper_runs_its_own_source_through_uv(tmp_path):
    root = _plugin(tmp_path)
    _fake(tmp_path / "uv-bin", "uv", "uv")
    result = _run(
        root / "bin" / "nichiyou-daiku",
        root / "bin",
        tmp_path / "uv-bin",
        _tools(tmp_path),
    )
    assert result.stdout.splitlines() == [
        "uv",
        "tool",
        "run",
        "--from",
        str(root),
        "nichiyou-daiku",
        "validate",
        "my table.nd",
    ]


@pytest.mark.parametrize(
    "args",
    [
        ("export", "d.nd"),
        ("drawing", "d.nd"),
        ("view", "d.nd"),
        ("-v", "export", "d.nd"),
    ],
)
def test_wrapper_adds_the_viz_extra_for_3d_commands(tmp_path, args):
    root = _plugin(tmp_path)
    _fake(tmp_path / "uv-bin", "uv", "uv")
    result = _run(
        root / "bin" / "nichiyou-daiku",
        tmp_path / "uv-bin",
        _tools(tmp_path),
        args=args,
    )
    assert result.stdout.splitlines()[3:5] == [
        "--from",
        f"nichiyou-daiku[viz] @ {root}",
    ]
    assert result.stdout.splitlines()[6:] == list(args)


def test_wrapper_keeps_a_plugin_path_with_spaces_whole(tmp_path):
    root = _plugin(tmp_path, "claude plugins")
    _fake(tmp_path / "uv-bin", "uv", "uv")
    result = _run(
        root / "bin" / "nichiyou-daiku", tmp_path / "uv-bin", _tools(tmp_path)
    )
    assert result.stdout.splitlines()[4] == str(root)


def test_wrapper_called_by_another_copy_goes_straight_to_uv(tmp_path):
    root = _plugin(tmp_path)
    _fake(tmp_path / "installed", "nichiyou-daiku", "installed")
    _fake(tmp_path / "uv-bin", "uv", "uv")
    result = _run(
        root / "bin" / "nichiyou-daiku",
        tmp_path / "installed",
        tmp_path / "uv-bin",
        _tools(tmp_path),
        env={"NICHIYOU_DAIKU_WRAPPED": "1"},
    )
    assert result.stdout.splitlines()[0] == "uv"


def test_copies_of_the_wrapper_do_not_call_each_other(tmp_path):
    first = _plugin(tmp_path, "first")
    second = _plugin(tmp_path, "second")
    _fake(tmp_path / "uv-bin", "uv", "uv")
    result = _run(
        first / "bin" / "nichiyou-daiku",
        first / "bin",
        second / "bin",
        tmp_path / "uv-bin",
        _tools(tmp_path),
    )
    lines = result.stdout.splitlines()
    assert lines[0] == "uv"
    assert lines[4] in (str(first), str(second))


def test_wrapper_reached_through_a_symlink_uses_the_plugin_root(tmp_path):
    root = _plugin(tmp_path)
    links = tmp_path / "links"
    links.mkdir()
    target = root / "bin" / "nichiyou-daiku"
    (links / "nichiyou-daiku").symlink_to(os.path.relpath(target, links))
    _fake(tmp_path / "uv-bin", "uv", "uv")
    result = _run(
        links / "nichiyou-daiku", links, tmp_path / "uv-bin", _tools(tmp_path)
    )
    assert result.stdout.splitlines()[4] == str(root)


def test_wrapper_skips_the_current_directory_and_directories(tmp_path):
    root = _plugin(tmp_path)
    _fake(tmp_path / "work", "nichiyou-daiku", "from the current directory")
    (tmp_path / "checkouts" / "nichiyou-daiku").mkdir(parents=True)
    _fake(tmp_path / "uv-bin", "uv", "uv")
    result = _run(
        root / "bin" / "nichiyou-daiku",
        "",  # an empty entry means the current directory
        tmp_path / "checkouts",
        tmp_path / "uv-bin",
        _tools(tmp_path),
        cwd=tmp_path / "work",
    )
    assert result.stdout.splitlines()[0] == "uv"


def test_wrapper_without_cli_or_uv_says_how_to_install(tmp_path):
    root = _plugin(tmp_path)
    result = _run(root / "bin" / "nichiyou-daiku", root / "bin", _tools(tmp_path))
    assert result.returncode == 127
    assert "https://docs.astral.sh/uv/" in result.stderr
    assert (
        'uv tool install "git+https://github.com/ar90n/nichiyou-daiku"' in result.stderr
    )


SKILLS = sorted((ROOT / "skills").glob("*/SKILL.md"))
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def test_the_design_skill_exists():
    assert ROOT / "skills" / "design" / "SKILL.md" in SKILLS


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parent.name)
def test_skill_frontmatter_names_and_describes_the_skill(path):
    header = FRONTMATTER.match(path.read_text())
    assert header is not None
    fields = dict(re.findall(r"^(\w+): (.+)$", header.group(1), re.M))
    assert fields["name"] == path.parent.name
    assert 0 < len(fields["description"]) <= 1024


def test_plugin_root_appears_only_in_skill_bodies():
    # Claude Code substitutes it in SKILL.md; a file read later keeps it literal
    literal = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "skills").rglob("*")
        if path.is_file()
        and path.name != "SKILL.md"
        and "${CLAUDE_PLUGIN_ROOT}" in path.read_text()
    ]
    assert literal == []
