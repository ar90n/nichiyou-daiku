"""The Claude Code plugin: manifests, skills and the CLI wrapper."""

import json
from pathlib import Path

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
