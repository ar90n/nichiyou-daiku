"""The checks run the nichiyou-daiku CLI: the one NICHIYOU_DAIKU_BIN names
(CI builds it), else this repository's debug build, built here if needed."""

import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).parents[2]


def pytest_configure(config):
    if os.environ.get("NICHIYOU_DAIKU_BIN"):
        return
    subprocess.run(
        ["cargo", "build", "--quiet", "-p", "nichiyou-daiku-cli"], cwd=REPO, check=True
    )
    os.environ["NICHIYOU_DAIKU_BIN"] = str(REPO / "target" / "debug" / "nichiyou-daiku")


@pytest.fixture(autouse=True)
def _no_cargo(monkeypatch):
    """An evaluation builds its CLI with cargo; the tests use the one above."""
    from evals.design import run

    monkeypatch.setattr(
        run, "build_cli", lambda plugin, into: Path(os.environ["NICHIYOU_DAIKU_BIN"])
    )
