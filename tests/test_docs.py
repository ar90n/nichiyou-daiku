"""Documentation must not point at code that no longer exists."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
DOCS = [
    "README.md",
    "docs/api-specification.md",
    "docs/api-specification_ja.md",
    "prompts/reference/python-api.md",
]
# Whole names only: "basic_joints.py" is an example that still exists
REMOVED = [
    r"(?<!\w)joints\.py",
    r"(?<!\w)projection\.py",
    r"joint positions and orientations",
    r"ジョイント位置と向き",
    r"\bJointPair\b",
    r"\bOrientation3D\b",
]


@pytest.mark.parametrize("doc", DOCS)
def test_docs_do_not_mention_removed_joint_code(doc):
    text = (ROOT / doc).read_text()
    assert [pattern for pattern in REMOVED if re.search(pattern, text)] == []
