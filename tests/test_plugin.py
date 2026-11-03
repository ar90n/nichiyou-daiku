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
VERSION = "9.9.9"


def _tools(tmp_path: Path) -> Path:
    """Only the utilities the wrapper needs to reach its cache, so a
    nichiyou-daiku installed on this machine stays out of the tests."""
    tools = tmp_path / "tools"
    tools.mkdir(exist_ok=True)
    for name in ("dirname", "basename", "readlink", "sed", "head", "uname"):
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
    """A plugin root holding a copy of the wrapper and the version it reads."""
    bin_dir = tmp_path / name / "bin"
    bin_dir.mkdir(parents=True)
    shutil.copy2(WRAPPER, bin_dir / "nichiyou-daiku")
    (tmp_path / name / "Cargo.toml").write_text(
        f'[workspace]\n\n[workspace.package]\nversion = "{VERSION}"\n'
    )
    return (tmp_path / name).resolve()


def _cached(cache_home: Path) -> Path:
    """This version's CLI, as the wrapper leaves it after downloading it."""
    _fake(cache_home / "nichiyou-daiku" / VERSION, "nichiyou-daiku", "cached")
    return cache_home


def _run(
    command: Path,
    *path: Path | str,
    cache: Path,
    args=("validate", "my table.nd"),
    env=None,
    cwd=None,
):
    return subprocess.run(
        [str(command), *args],
        env={
            "PATH": os.pathsep.join(str(p) for p in path),
            "XDG_CACHE_HOME": str(cache),
            **(env or {}),
        },
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
    dirs = [tmp_path / "installed", root / "bin"]
    if not installed_first:
        dirs.reverse()
    result = _run(
        root / "bin" / "nichiyou-daiku",
        *dirs,
        _tools(tmp_path),
        cache=_cached(tmp_path / "cache"),
    )
    assert result.stdout.splitlines() == ["installed", "validate", "my table.nd"]


def test_wrapper_runs_the_cli_its_version_downloaded(tmp_path):
    root = _plugin(tmp_path)
    result = _run(
        root / "bin" / "nichiyou-daiku",
        root / "bin",
        _tools(tmp_path),
        cache=_cached(tmp_path / "cache"),
    )
    assert result.stdout.splitlines() == ["cached", "validate", "my table.nd"]


def test_wrapper_keeps_the_cli_outside_the_plugin(tmp_path):
    # The plugin directory is replaced on every update: the downloaded CLI
    # lives in the user's cache, ~/.cache without XDG_CACHE_HOME
    root = _plugin(tmp_path)
    home = tmp_path / "home"
    _cached(home / ".cache")
    result = _run(
        root / "bin" / "nichiyou-daiku",
        _tools(tmp_path),
        cache=Path(""),
        env={"XDG_CACHE_HOME": "", "HOME": str(home)},
    )
    assert result.stdout.splitlines()[0] == "cached"


def test_wrapper_keeps_a_plugin_path_with_spaces_whole(tmp_path):
    # The version comes from the plugin root, so a root broken at its space
    # would not find this version's CLI
    root = _plugin(tmp_path, "claude plugins")
    result = _run(
        root / "bin" / "nichiyou-daiku",
        _tools(tmp_path),
        cache=_cached(tmp_path / "cache"),
    )
    assert result.stdout.splitlines()[0] == "cached"


def test_wrapper_called_by_another_copy_goes_straight_to_its_cache(tmp_path):
    root = _plugin(tmp_path)
    _fake(tmp_path / "installed", "nichiyou-daiku", "installed")
    result = _run(
        root / "bin" / "nichiyou-daiku",
        tmp_path / "installed",
        _tools(tmp_path),
        cache=_cached(tmp_path / "cache"),
        env={"NICHIYOU_DAIKU_WRAPPED": "1"},
    )
    assert result.stdout.splitlines()[0] == "cached"


def test_copies_of_the_wrapper_do_not_call_each_other(tmp_path):
    first = _plugin(tmp_path, "first")
    second = _plugin(tmp_path, "second")
    result = _run(
        first / "bin" / "nichiyou-daiku",
        first / "bin",
        second / "bin",
        _tools(tmp_path),
        cache=_cached(tmp_path / "cache"),
    )
    assert result.stdout.splitlines()[0] == "cached"


def test_wrapper_reached_through_a_symlink_uses_the_plugin_root(tmp_path):
    root = _plugin(tmp_path)
    links = tmp_path / "links"
    links.mkdir()
    target = root / "bin" / "nichiyou-daiku"
    (links / "nichiyou-daiku").symlink_to(os.path.relpath(target, links))
    result = _run(
        links / "nichiyou-daiku",
        links,
        _tools(tmp_path),
        cache=_cached(tmp_path / "cache"),
    )
    assert result.stdout.splitlines()[0] == "cached"


def test_wrapper_skips_the_current_directory_and_directories(tmp_path):
    root = _plugin(tmp_path)
    _fake(tmp_path / "work", "nichiyou-daiku", "from the current directory")
    (tmp_path / "checkouts" / "nichiyou-daiku").mkdir(parents=True)
    result = _run(
        root / "bin" / "nichiyou-daiku",
        "",  # an empty entry means the current directory
        tmp_path / "checkouts",
        _tools(tmp_path),
        cache=_cached(tmp_path / "cache"),
        cwd=tmp_path / "work",
    )
    assert result.stdout.splitlines()[0] == "cached"


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


def test_the_skill_reads_the_specification_up_to_its_complete_examples():
    # The examples, CLI, grammar and error sections after that line are not
    # needed to design, and every line read stays in the agent's context
    skill = (ROOT / "skills" / "design" / "SKILL.md").read_text()
    found = re.search(r"its first (\d+) lines", skill)
    assert found, "SKILL.md names how many lines of the specification to read"
    spec = (ROOT / "docs" / "dsl-specification.md").read_text().splitlines()
    assert spec[int(found.group(1))].startswith("## Complete Examples")


def test_the_skill_does_not_rely_on_claude_code_s_plugin_root():
    # Only Claude Code substitutes it: opencode and other tools read the same
    # skill, so files are linked relative to the skill instead
    literal = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "skills").rglob("*")
        if path.is_file() and "${CLAUDE_PLUGIN_ROOT}" in path.read_text()
    ]
    assert literal == []


def test_skill_tells_how_to_reinstall_the_cli():
    # An installed CLI can lack the viz extra or be older than the plugin's
    # docs; the skill names the README's install commands to fix that
    commands = re.findall(
        r'`(uv tool install (?:--force )?"[^"`]+")`',
        (ROOT / "skills" / "design" / "SKILL.md").read_text(),
    )
    readme = (ROOT / "README.md").read_text()
    assert commands
    assert [c for c in commands if c.replace("--force ", "") not in readme] == []


def test_skill_covers_an_installed_cli_without_json():
    # A CLI installed before validate --json rejects the option
    skill = (ROOT / "skills" / "design" / "SKILL.md").read_text()
    assert "No such option: --json" in skill


def test_skill_covers_render_with_an_old_or_partial_install():
    # Step 6 is the first command that needs the viz extra and cairo
    skill = (ROOT / "skills" / "design" / "SKILL.md").read_text()
    assert "No such command 'render'" in skill
    assert "`drawing`, `export`, `render` or `steps` says build123d is missing" in skill
    assert "the cairo library is missing" in skill
