# 部材配置のコア移行 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 全接続を同時に満たす部材配置をコア（`core/placement.py`）で厳密に計算し、build123d はその位置にソリッドを置くだけにする。

**Architecture:** 接続ごとに target→base の相対回転（90° 刻みの符号付き置換行列）を求め、群を併合しながら回転を伝播する。
回転を各群の最初に宣言された部材の座標系に正規化してから、並進を X/Y/Z 軸ごとの差分制約として重み付き Union-Find で厳密に解く。
矛盾は先に宣言した接続を優先して報告し、つながっていない群は +X 方向に並べる。`Assembly.of` が `placement` を持ち、shell と CLI はそれを使う。

**Tech Stack:** Python 3.13, pydantic（frozen モデル）, numpy, pytest, hypothesis, build123d（shell のみ・任意依存）, Click

**Spec:** `docs/superpowers/specs/2026-10-11-core-placement-design.md`

## Global Constraints

- 新しい依存を追加しない（numpy・pydantic のみで解く。scipy 等は使わない）。
- データクラスは frozen な pydantic モデル（既存規約）。
- 回転は成分 −1/0/1 の整数行列（各行・各列に非零 1 つ、行列式 +1）。近似しない。
- 並進は最小二乗を使わず軸ごとに厳密に解く。許容誤差 `TOLERANCE_MM = 1e-6`。位置は `round(v, 6) + 0.0` で丸める。
- 矛盾時は先に宣言した接続を優先し、矛盾した拘束だけを報告する。矛盾のないモデルでは結果は接続順に依存しない。
- つながっていない群は 2 つ目以降を直前までの外形の最大 X から `GROUP_GAP_MM = 100.0` 離して +X 方向に並べる。
- `validate` は矛盾・未接続・重なり・部材外ダボを終了コード 1 で報告。`export` / `report` / `view` / `drawing` は警告して終了コード 0 で続行。
- コミットメッセージは既存の Conventional Commits 形式（`feat:` `refactor:` `test:` `docs:` …、件名は大文字始まり）。ドットファイルはコミットしない。`CLAUDE.md` は git 管理外（ローカル更新のみ）。
- 各タスクのコミット前に `make lint` と `make test`（カバレッジ 90% 以上）を通す。最終タスクで `make ci-local` を通す。

## Review Focus

1. 小数の長さ・オフセットでループを閉じても誤った矛盾が出ないこと → Task 2 `test_fractional_loop_closes_without_conflicts`
2. 空のモデル・部材 1 本・接続のない部材でも落ちずに配置できること → Task 2 `test_empty_model` / `test_single_piece_sits_at_origin`
3. 回転が矛盾した接続から、並進の偽の矛盾が二重に報告されないこと → Task 2 `test_rotation_conflict_is_reported_once`
4. 1x4（厚み 19mm）を含む混在モデルでも配置規則が成り立つこと → Task 2 のプロパティテストの生成器に `PT_1x4` を含める
5. 並べた別の群どうしが重なりとして報告されないこと → Task 3 `test_laid_out_groups_do_not_overlap`

---

## File Structure

| ファイル | 役割 | 変更 |
|---|---|---|
| `src/nichiyou_daiku/core/placement.py` | Pose / Conflict / Placement / Overlap、相対回転、ソルバー、重なり、外形 | 新規（Task 1–3） |
| `src/nichiyou_daiku/core/assembly/builder.py` | `Assembly.placement` を追加 | 変更（Task 4） |
| `src/nichiyou_daiku/shell/build123d_export.py` | Pose でソリッドを置くだけにする。RigidJoint・旧チェックを削除 | 変更（Task 6） |
| `src/nichiyou_daiku/shell/__init__.py` | 公開名の整理 | 変更（Task 6） |
| `src/nichiyou_daiku/shell/resources.py` | `ResourceSummary.overall_size` / `size_reference` | 変更（Task 7） |
| `src/nichiyou_daiku/shell/report_generator.py` | 概要に外形寸法 | 変更（Task 7） |
| `src/nichiyou_daiku/cli/utils.py` | `describe_placement_issues`, `warn_placement_issues` | 変更（Task 5, 7） |
| `src/nichiyou_daiku/cli/commands/validate.py` | コアで検証（build123d 不要）。`--no-geometry` 削除 | 変更（Task 5） |
| `tests/core/test_placement.py` | ソルバーの単体・プロパティテスト | 新規（Task 1–3） |
| `tests/core/fixtures/placement_examples.json` | 移行前の build123d 配置から作る期待値 | 新規（Task 4） |
| `tests/core/test_placement_examples.py` | 期待値固定の回帰テスト | 新規（Task 4） |
| `tests/shell/test_placement_matches_build123d.py` | 移行前の照合テスト（Task 6 で削除） | 新規（Task 4） |
| `tests/shell/test_build123d_geometry.py` / `test_build123d_export.py` | 旧チェックのテスト削除、描画位置のテスト追加 | 変更（Task 6） |
| `tests/cli/test_validate.py`, `tests/cli/test_placement_warnings.py`, `tests/shell/test_resources.py`, `tests/shell/test_report_generator.py` | CLI・レポート | 変更/新規（Task 5, 7） |
| `README.md`, `docs/api-specification*.md` | ドキュメント | 変更（Task 8） |

---

### Task 1: Pose・結果モデル・相対回転

**Files:**
- Create: `src/nichiyou_daiku/core/placement.py`
- Test: `tests/core/test_placement.py`

**Interfaces:**
- Produces:
  - `Axis = Literal["x","y","z"]`, `ConstraintKind = Literal["rotation","contact","flush","edge"]`, `Matrix3`, `AXES`, `TOLERANCE_MM`, `GROUP_GAP_MM`, `IDENTITY`
  - `class Pose(rotation: Matrix3 = IDENTITY, translation: tuple[float,float,float] = (0,0,0))` with `rotation_matrix() -> np.ndarray`, `apply(point: Point3D) -> Point3D`, `bounds(piece: Piece) -> tuple[Point3D, Point3D]`
  - `class Conflict(base_id: str, target_id: str, kind: ConstraintKind, axis: Axis | None = None, mismatch_mm: float | None = None, loop: tuple[str, ...])`
  - `class Placement(poses: dict[str, Pose], groups: tuple[tuple[str, ...], ...], conflicts: tuple[Conflict, ...] = (), free_axes: dict[str, frozenset[Axis]] = {})`
  - `class Overlap(lhs: str, rhs: str, volume: float)`
  - `relative_rotation(base: BoundAnchor, target: BoundAnchor) -> np.ndarray`（int 3x3）
  - private: `_normal(face: Face) -> np.ndarray`

- [ ] **Step 1: Write the failing tests**

`tests/core/test_placement.py`:

```python
"""Tests for solving piece placement from connections."""

import numpy as np
import pytest

from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.geometry import FromMin, Point3D, Vector3D, is_adjacent
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.placement import Pose, relative_rotation

FACES = ["top", "down", "left", "right", "front", "back"]
ADJACENT = [(c, e) for c in FACES for e in FACES if is_adjacent(c, e)]


def _vec(face) -> np.ndarray:
    v = Vector3D.normal_of(face)
    return np.array([v.x, v.y, v.z])


def _bound(piece: Piece, contact, edge) -> BoundAnchor:
    return BoundAnchor(
        piece=piece,
        anchor=Anchor(contact_face=contact, edge_shared_face=edge, offset=FromMin(value=0)),
    )


class TestPose:
    def test_identity_pose_leaves_points_alone(self):
        point = Point3D(x=1.0, y=2.0, z=3.0)
        assert Pose().apply(point) == point

    def test_bounds_of_rotated_and_moved_piece(self):
        piece = Piece.of(PieceType.PT_2x4, 500.0, "p")
        # local (x, y, z) -> (-y, x, z), then +10 along X
        pose = Pose(rotation=((0, -1, 0), (1, 0, 0), (0, 0, 1)), translation=(10.0, 0.0, 0.0))
        low, high = pose.bounds(piece)
        assert (low.x, low.y, low.z) == (-28.0, 0.0, 0.0)
        assert (high.x, high.y, high.z) == (10.0, 89.0, 500.0)


class TestRelativeRotation:
    @pytest.mark.parametrize("base_faces", ADJACENT)
    @pytest.mark.parametrize("target_faces", ADJACENT)
    def test_is_a_proper_signed_permutation(self, base_faces, target_faces):
        a = Piece.of(PieceType.PT_2x4, 500.0, "a")
        b = Piece.of(PieceType.PT_2x4, 300.0, "b")
        rotation = relative_rotation(_bound(a, *base_faces), _bound(b, *target_faces))
        assert rotation.dtype.kind == "i"
        assert set(np.abs(rotation).sum(axis=0)) == {1}
        assert set(np.abs(rotation).sum(axis=1)) == {1}
        assert round(np.linalg.det(rotation)) == 1

    @pytest.mark.parametrize("base_faces", ADJACENT)
    @pytest.mark.parametrize("target_faces", ADJACENT)
    def test_contact_faces_meet_and_edge_faces_are_flush(self, base_faces, target_faces):
        a = Piece.of(PieceType.PT_2x4, 500.0, "a")
        b = Piece.of(PieceType.PT_2x4, 300.0, "b")
        rotation = relative_rotation(_bound(a, *base_faces), _bound(b, *target_faces))
        assert np.array_equal(rotation @ _vec(target_faces[0]), -_vec(base_faces[0]))
        assert np.array_equal(rotation @ _vec(target_faces[1]), _vec(base_faces[1]))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_placement.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'nichiyou_daiku.core.placement'`

- [ ] **Step 3: Write the implementation**

`src/nichiyou_daiku/core/placement.py`:

```python
"""Solve piece placement from connections.

Each connection fixes the target's orientation (a multiple of 90 degrees)
and its position relative to the base. Orientations are propagated exactly;
positions are solved per world axis as difference constraints, so every
accepted constraint holds exactly and contradictions are reported rather
than averaged out.
"""

from typing import Literal

import numpy as np
from pydantic import BaseModel

from .anchor import BoundAnchor
from .geometry import Face, Point3D, Vector3D
from .piece import Piece, get_shape

Axis = Literal["x", "y", "z"]
ConstraintKind = Literal["rotation", "contact", "flush", "edge"]
Matrix3 = tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]

AXES: tuple[Axis, Axis, Axis] = ("x", "y", "z")
TOLERANCE_MM = 1e-6
GROUP_GAP_MM = 100.0
IDENTITY: Matrix3 = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


class Pose(BaseModel, frozen=True):
    """Where a piece sits in the world: a 90-degree rotation and a translation.

    A local point p maps to ``rotation @ p + translation``.
    """

    rotation: Matrix3 = IDENTITY
    translation: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def rotation_matrix(self) -> np.ndarray:
        return np.array(self.rotation, dtype=float)

    def apply(self, point: Point3D) -> Point3D:
        x, y, z = self.rotation_matrix() @ np.array(
            [point.x, point.y, point.z]
        ) + np.array(self.translation)
        return Point3D(x=float(x), y=float(y), z=float(z))

    def bounds(self, piece: Piece) -> tuple[Point3D, Point3D]:
        """World axis-aligned bounding box of the piece."""
        shape = get_shape(piece)
        corners = np.array(
            [
                [x, y, z]
                for x in (0.0, shape.width)
                for y in (0.0, shape.height)
                for z in (0.0, shape.length)
            ]
        )
        world = corners @ self.rotation_matrix().T + np.array(self.translation)
        low, high = world.min(axis=0), world.max(axis=0)
        return (
            Point3D(x=float(low[0]), y=float(low[1]), z=float(low[2])),
            Point3D(x=float(high[0]), y=float(high[1]), z=float(high[2])),
        )


class Conflict(BaseModel, frozen=True):
    """A connection constraint that contradicts the ones accepted before it.

    ``loop`` is the path of pieces from base to target through the accepted
    constraints that the conflicting one would close.
    """

    base_id: str
    target_id: str
    kind: ConstraintKind
    axis: Axis | None = None
    mismatch_mm: float | None = None
    loop: tuple[str, ...]


class Placement(BaseModel, frozen=True):
    """Solved placement of every piece in a model.

    ``free_axes`` lists, per piece, the world axes along which nothing ties
    it to its group's first piece. Current connections constrain all three
    axes, so it is empty.
    """

    poses: dict[str, Pose]
    groups: tuple[tuple[str, ...], ...]
    conflicts: tuple[Conflict, ...] = ()
    free_axes: dict[str, frozenset[Axis]] = {}


class Overlap(BaseModel, frozen=True):
    """Two pieces whose boxes share volume (mm³)."""

    lhs: str
    rhs: str
    volume: float


def _normal(face: Face) -> np.ndarray:
    v = Vector3D.normal_of(face)
    return np.array([v.x, v.y, v.z])


def _frame(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    return np.column_stack([first, second, np.cross(first, second)])


def relative_rotation(base: BoundAnchor, target: BoundAnchor) -> np.ndarray:
    """Rotation taking target-local directions to base-local directions.

    The contact faces face each other and the edge-shared faces face the
    same way (flush).
    """
    n_base = _normal(base.anchor.contact_face)
    e_base = _normal(base.anchor.edge_shared_face)
    n_target = _normal(target.anchor.contact_face)
    e_target = _normal(target.anchor.edge_shared_face)
    rotation = _frame(-n_base, e_base) @ _frame(n_target, e_target).T
    return np.rint(rotation).astype(int)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_placement.py -q`
Expected: PASS（1154 passed: Pose 2 件 + 576×2 件）

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff format src/nichiyou_daiku/core/placement.py tests/core/test_placement.py
make lint
git add src/nichiyou_daiku/core/placement.py tests/core/test_placement.py
git commit -m "feat(core): Add placement pose model and relative rotation"
```

---

### Task 2: ソルバー `solve_placement`

**Files:**
- Modify: `src/nichiyou_daiku/core/placement.py`
- Test: `tests/core/test_placement.py`

**Interfaces:**
- Consumes: Task 1 の全シンボル
- Produces: `solve_placement(model: Model) -> Placement`

- [ ] **Step 1: Write the failing tests**

`tests/core/test_placement.py` の import を次に置き換え、末尾にテストを追加する。

```python
"""Tests for solving piece placement from connections."""

from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from nichiyou_daiku.core.anchor import Anchor, BoundAnchor, as_point_3d
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.geometry import (
    Box,
    Edge,
    FromMax,
    FromMin,
    Point3D,
    Vector3D,
    edge_length_of,
    is_adjacent,
)
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
from nichiyou_daiku.core.placement import Pose, relative_rotation, solve_placement
from nichiyou_daiku.dsl import parse_dsl
```

```python
TABLE = (
    Path(__file__).parents[2] / "examples" / "nd_files" / "simple_table_compact.nd"
).read_text()
TABLE_LOOP_CLOSER = "leg_4 -[FL<100 TF<0]- apron_right"


def _box(placement, model, piece_id):
    low, high = placement.poses[piece_id].bounds(model.pieces[piece_id])
    return (low.x, low.y, low.z, high.x, high.y, high.z)


@st.composite
def anchors_on(draw, piece: Piece) -> Anchor:
    contact, edge = draw(st.sampled_from(ADJACENT))
    length = edge_length_of(Box(shape=get_shape(piece)), Edge(lhs=contact, rhs=edge))
    value = draw(st.floats(min_value=0, max_value=length, allow_nan=False))
    offset = draw(st.sampled_from([FromMin, FromMax]))(value=value)
    return Anchor(contact_face=contact, edge_shared_face=edge, offset=offset)


@st.composite
def tree_models(draw) -> Model:
    count = draw(st.integers(min_value=2, max_value=6))
    pieces = [
        Piece.of(
            draw(st.sampled_from([PieceType.PT_2x4, PieceType.PT_1x4])),
            draw(st.floats(min_value=50, max_value=1500, allow_nan=False)),
            f"p{i}",
        )
        for i in range(count)
    ]
    connections = []
    for i in range(1, count):
        base = pieces[draw(st.integers(min_value=0, max_value=i - 1))]
        connections.append(
            Connection(
                base=BoundAnchor(piece=base, anchor=draw(anchors_on(base))),
                target=BoundAnchor(piece=pieces[i], anchor=draw(anchors_on(pieces[i]))),
            )
        )
    return Model.of(pieces=pieces, connections=connections)


class TestSolvePlacement:
    def test_empty_model(self):
        placement = solve_placement(Model.of(pieces=[], connections=[]))
        assert placement.poses == {}
        assert placement.groups == ()

    def test_single_piece_sits_at_origin(self):
        placement = solve_placement(parse_dsl("(a:2x4 =500)"))
        assert placement.poses == {"a": Pose()}
        assert placement.groups == (("a",),)

    def test_target_is_placed_against_the_base_contact_face(self):
        model = parse_dsl("(a:2x4 =500)\n(b:2x4 =300)\na -[FL<100 DF<0]- b\n")
        placement = solve_placement(model)
        assert placement.poses["a"] == Pose()
        # b's down end touches a's front face (y=38) 100mm above a's down end
        assert _box(placement, model, "b") == (0.0, 38.0, 11.0, 38.0, 338.0, 100.0)

    def test_table_has_no_conflicts_and_one_group(self):
        placement = solve_placement(parse_dsl(TABLE))
        assert placement.conflicts == ()
        assert len(placement.groups) == 1
        assert placement.free_axes == {}

    def test_table_placement_does_not_depend_on_connection_order(self):
        model = parse_dsl(TABLE)
        connections = list(model.connections.values())
        expected = solve_placement(model).poses
        for reordered in (connections[::-1], connections[3:] + connections[:3]):
            shuffled = Model.of(pieces=list(model.pieces.values()), connections=reordered)
            assert solve_placement(shuffled).poses == expected

    def test_fractional_loop_closes_without_conflicts(self):
        source = (
            TABLE.replace("=622)", "=622.37)")
            .replace("=524)", "=523.91)")
            .replace("<100 ", "<100.123 ")
        )
        assert solve_placement(parse_dsl(source)).conflicts == ()

    def test_contradicting_position_is_reported_and_earlier_connection_wins(self):
        model = parse_dsl(
            "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\n"
            "a -[FL<100 DF<0]- b\na -[FL>100 DF<0]- c\nb -[RF<0 LF<0]- c\n"
        )
        placement = solve_placement(model)
        (conflict,) = placement.conflicts
        assert (conflict.base_id, conflict.target_id) == ("b", "c")
        assert (conflict.kind, conflict.axis) == ("contact", "z")
        assert conflict.mismatch_mm == pytest.approx(-389.0)
        assert conflict.loop == ("b", "a", "c")
        # c stays where a -[FL>100 DF<0]- c put it
        alone = parse_dsl("(a:2x4 =500)\n(c:2x4 =300)\na -[FL>100 DF<0]- c\n")
        assert _box(placement, model, "c") == _box(solve_placement(alone), alone, "c")

    def test_flush_conflict_is_named(self):
        placement = solve_placement(
            parse_dsl(
                "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\n"
                "a -[RF<0 LF<0]- b\na -[FL<100 DF<0]- c\nb -[FL<100 DF<0]- c\n"
            )
        )
        (conflict,) = placement.conflicts
        assert (conflict.kind, conflict.axis, conflict.mismatch_mm) == ("flush", "x", 89.0)

    def test_rotation_conflict_is_reported_once(self):
        placement = solve_placement(
            parse_dsl(
                "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\n"
                "a -[RF<0 LF<0]- b\na -[FL<100 DF<0]- c\nb -[RF<0 LF<0]- c\n"
            )
        )
        (conflict,) = placement.conflicts
        assert conflict.kind == "rotation"
        assert conflict.axis is None and conflict.mismatch_mm is None
        assert conflict.loop == ("b", "a", "c")

    def test_unconnected_groups_are_laid_out_side_by_side(self):
        placement = solve_placement(
            parse_dsl("(a:2x4 =500)\n(b:2x4 =300)\n(floating:2x4 =300)\na -[FL<100 DF<0]- b\n")
        )
        assert placement.groups == (("a", "b"), ("floating",))
        # the first group ends at x=89; the next starts 100mm further
        assert placement.poses["floating"] == Pose(translation=(189.0, 0.0, 0.0))


@given(tree_models())
@settings(max_examples=200, deadline=None)
def test_every_connection_holds_in_a_tree(model):
    placement = solve_placement(model)
    assert placement.conflicts == ()
    assert len(placement.groups) == 1
    for connection in model.connections.values():
        base_pose = placement.poses[connection.base.piece.id]
        target_pose = placement.poses[connection.target.piece.id]
        a = base_pose.apply(as_point_3d(connection.base))
        b = target_pose.apply(as_point_3d(connection.target))
        assert (a.x, a.y, a.z) == pytest.approx((b.x, b.y, b.z), abs=1e-5)
        base_rot, target_rot = base_pose.rotation_matrix(), target_pose.rotation_matrix()
        assert np.array_equal(
            base_rot @ _vec(connection.base.anchor.contact_face),
            -(target_rot @ _vec(connection.target.anchor.contact_face)),
        )
        assert np.array_equal(
            base_rot @ _vec(connection.base.anchor.edge_shared_face),
            target_rot @ _vec(connection.target.anchor.edge_shared_face),
        )


@given(tree_models())
@settings(max_examples=200, deadline=None)
def test_rotations_are_proper_signed_permutations(model):
    for pose in solve_placement(model).poses.values():
        rotation = np.array(pose.rotation)
        assert set(np.abs(rotation).sum(axis=0)) == {1}
        assert set(np.abs(rotation).sum(axis=1)) == {1}
        assert round(np.linalg.det(rotation)) == 1


@given(tree_models(), st.randoms(use_true_random=False))
@settings(max_examples=200, deadline=None)
def test_connection_order_does_not_matter(model, rng):
    connections = list(model.connections.values())
    rng.shuffle(connections)
    shuffled = Model.of(pieces=list(model.pieces.values()), connections=connections)
    expected = solve_placement(model).poses
    actual = solve_placement(shuffled).poses
    # Rotations are exact; random float offsets may round differently at 1e-6
    for piece_id, pose in expected.items():
        assert actual[piece_id].rotation == pose.rotation
        assert actual[piece_id].translation == pytest.approx(pose.translation, abs=1e-5)


@given(st.floats(min_value=0.5, max_value=500, allow_nan=False))
@settings(max_examples=50, deadline=None)
def test_shifting_a_loop_closing_connection_reports_exactly_that_shift(shift):
    source = TABLE.replace(TABLE_LOOP_CLOSER, f"leg_4 -[FL<{100 + shift} TF<0]- apron_right")
    (conflict,) = solve_placement(parse_dsl(source)).conflicts
    assert (conflict.base_id, conflict.target_id) == ("leg_4", "apron_right")
    assert (conflict.kind, conflict.axis) == ("edge", "z")
    assert conflict.mismatch_mm == pytest.approx(shift, abs=1e-5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_placement.py -q`
Expected: collection error `ImportError: cannot import name 'solve_placement'`

- [ ] **Step 3: Write the implementation**

`src/nichiyou_daiku/core/placement.py` の import を次に置き換える。

```python
from collections import deque
from typing import Literal

import numpy as np
from pydantic import BaseModel

from .anchor import BoundAnchor, as_point_3d
from .connection import Connection
from .geometry import Face, Point3D, Vector3D
from .model import Model
from .piece import Piece, get_shape
```

`relative_rotation` の後ろに追加する。

```python
def _anchor_point(bound: BoundAnchor) -> np.ndarray:
    point = as_point_3d(bound)
    return np.array([point.x, point.y, point.z])


def _axis_index(direction: np.ndarray) -> int:
    return int(np.argmax(np.abs(direction)))


def _path(adjacency: dict[str, list[str]], start: str, goal: str) -> tuple[str, ...]:
    """Shortest path from start to goal; neighbours in insertion order."""
    previous: dict[str, str | None] = {start: None}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == goal:
            break
        for neighbour in adjacency.get(node, []):
            if neighbour not in previous:
                previous[neighbour] = node
                queue.append(neighbour)
    path = [goal]
    while (step := previous.get(path[-1])) is not None:
        path.append(step)
    return tuple(reversed(path))


class _AxisOffsets:
    """Weighted union-find along one axis: offset[x] is t[x] - t[parent[x]]."""

    def __init__(self, ids: list[str]) -> None:
        self.parent = {i: i for i in ids}
        self.offset = {i: 0.0 for i in ids}

    def find(self, node: str) -> tuple[str, float]:
        """Root of ``node`` and t[node] - t[root]."""
        path = []
        while self.parent[node] != node:
            path.append(node)
            node = self.parent[node]
        root = node
        total = 0.0
        for item in reversed(path):
            total += self.offset[item]
            self.offset[item] = total
            self.parent[item] = root
        return root, (self.offset[path[0]] if path else 0.0)

    def require(self, base: str, target: str, difference: float) -> float | None:
        """Require t[target] - t[base] == difference; return the mismatch if not."""
        base_root, base_offset = self.find(base)
        target_root, target_offset = self.find(target)
        if base_root == target_root:
            mismatch = difference - (target_offset - base_offset)
            return None if abs(mismatch) <= TOLERANCE_MM else mismatch
        self.parent[target_root] = base_root
        self.offset[target_root] = difference + base_offset - target_offset
        return None


def _round(value: float) -> float:
    return round(float(value), 6) + 0.0


def solve_placement(model: Model) -> Placement:
    """Place every piece so that all consistent connection constraints hold.

    Connections are taken in declaration order; a constraint that contradicts
    the ones accepted before it is reported in ``conflicts`` and ignored.
    """
    piece_ids = list(model.pieces)
    rotation = {pid: np.eye(3, dtype=int) for pid in piece_ids}
    group_of = {pid: pid for pid in piece_ids}
    members = {pid: [pid] for pid in piece_ids}
    conflicts: list[Conflict] = []
    accepted: list[Connection] = []
    rotation_graph: dict[str, list[str]] = {}

    # Step 1: orientations
    for connection in model.connections.values():
        base_id, target_id = connection.base.piece.id, connection.target.piece.id
        required = rotation[base_id] @ relative_rotation(connection.base, connection.target)
        if group_of[base_id] == group_of[target_id]:
            if not np.array_equal(rotation[target_id], required):
                conflicts.append(
                    Conflict(
                        base_id=base_id,
                        target_id=target_id,
                        kind="rotation",
                        loop=_path(rotation_graph, base_id, target_id),
                    )
                )
                continue
        else:
            correction = required @ rotation[target_id].T
            moved = group_of[target_id]
            for member in members[moved]:
                rotation[member] = correction @ rotation[member]
                group_of[member] = group_of[base_id]
            members[group_of[base_id]].extend(members.pop(moved))
        accepted.append(connection)
        rotation_graph.setdefault(base_id, []).append(target_id)
        rotation_graph.setdefault(target_id, []).append(base_id)

    # Express every group in the frame of its first declared piece, so the
    # position constraints below are written in world axes.
    order = {pid: i for i, pid in enumerate(piece_ids)}
    groups = sorted(
        (sorted(group, key=order.__getitem__) for group in members.values()),
        key=lambda group: order[group[0]],
    )
    for group in groups:
        to_root = rotation[group[0]].T
        for member in group:
            rotation[member] = to_root @ rotation[member]

    # Step 2: positions, one world axis at a time
    offsets = {axis: _AxisOffsets(piece_ids) for axis in AXES}
    axis_graph: dict[Axis, dict[str, list[str]]] = {axis: {} for axis in AXES}
    for connection in accepted:
        base_id, target_id = connection.base.piece.id, connection.target.piece.id
        base_rot, target_rot = rotation[base_id], rotation[target_id]
        difference = base_rot @ _anchor_point(connection.base) - target_rot @ _anchor_point(
            connection.target
        )
        kinds: dict[int, ConstraintKind] = {
            _axis_index(base_rot @ _normal(connection.base.anchor.contact_face)): "contact",
            _axis_index(base_rot @ _normal(connection.base.anchor.edge_shared_face)): "flush",
        }
        for index, axis in enumerate(AXES):
            mismatch = offsets[axis].require(base_id, target_id, float(difference[index]))
            if mismatch is None:
                axis_graph[axis].setdefault(base_id, []).append(target_id)
                axis_graph[axis].setdefault(target_id, []).append(base_id)
            else:
                conflicts.append(
                    Conflict(
                        base_id=base_id,
                        target_id=target_id,
                        kind=kinds.get(index, "edge"),
                        axis=axis,
                        mismatch_mm=_round(mismatch),
                        loop=_path(axis_graph[axis], base_id, target_id),
                    )
                )

    # Step 3: positions relative to each group's first declared piece
    poses: dict[str, Pose] = {}
    free_axes: dict[str, frozenset[Axis]] = {}
    for group in groups:
        root = group[0]
        root_position = np.array([offsets[axis].find(root)[1] for axis in AXES])
        for member in group:
            position = np.array([offsets[axis].find(member)[1] for axis in AXES])
            free: frozenset[Axis] = frozenset(
                axis
                for axis in AXES
                if offsets[axis].find(member)[0] != offsets[axis].find(root)[0]
            )
            if free:
                free_axes[member] = free
            matrix = rotation[member]
            poses[member] = Pose(
                rotation=(
                    (int(matrix[0, 0]), int(matrix[0, 1]), int(matrix[0, 2])),
                    (int(matrix[1, 0]), int(matrix[1, 1]), int(matrix[1, 2])),
                    (int(matrix[2, 0]), int(matrix[2, 1]), int(matrix[2, 2])),
                ),
                translation=(
                    _round(position[0] - root_position[0]),
                    _round(position[1] - root_position[1]),
                    _round(position[2] - root_position[2]),
                ),
            )

    # Step 4: lay unconnected groups side by side along +X
    right_edge: float | None = None
    for group in groups:
        low_x = min(poses[m].bounds(model.pieces[m])[0].x for m in group)
        high_x = max(poses[m].bounds(model.pieces[m])[1].x for m in group)
        shift = 0.0 if right_edge is None else right_edge + GROUP_GAP_MM - low_x
        if shift:
            for member in group:
                x, y, z = poses[member].translation
                poses[member] = Pose(
                    rotation=poses[member].rotation, translation=(_round(x + shift), y, z)
                )
        right_edge = high_x + shift if right_edge is None else max(right_edge, high_x + shift)

    return Placement(
        poses=poses,
        groups=tuple(tuple(group) for group in groups),
        conflicts=tuple(conflicts),
        free_axes=free_axes,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_placement.py -q`
Expected: PASS（全件）

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff format src/nichiyou_daiku/core/placement.py tests/core/test_placement.py
make lint && make test
git add src/nichiyou_daiku/core/placement.py tests/core/test_placement.py
git commit -m "feat(core): Solve piece placement exactly from all connections"
```

---

### Task 3: 重なりと外形

**Files:**
- Modify: `src/nichiyou_daiku/core/placement.py`
- Test: `tests/core/test_placement.py`

**Interfaces:**
- Consumes: `Placement`, `Pose.bounds`, `Overlap`, `TOLERANCE_MM`, `solve_placement`
- Produces: `find_overlaps(model: Model, placement: Placement) -> tuple[Overlap, ...]`, `overall_bounds(model: Model, placement: Placement) -> tuple[Point3D, Point3D]`

- [ ] **Step 1: Write the failing tests**

import に `find_overlaps, overall_bounds` を追加し（`from nichiyou_daiku.core.placement import Pose, find_overlaps, overall_bounds, relative_rotation, solve_placement`）、末尾に追加する。

```python
class TestOverlaps:
    def test_touching_pieces_do_not_overlap(self):
        model = parse_dsl("(a:2x4 =500)\n(b:2x4 =300)\na -[FL<100 DF<0]- b\n")
        assert find_overlaps(model, solve_placement(model)) == ()

    def test_every_overlapping_pair_is_reported_with_its_volume(self):
        model = parse_dsl(
            "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\n(d:2x4 =300)\n(e:2x4 =300)\n"
            "a -[FL<100 DF<0]- b\na -[FL<100 DF<0]- c\n"
            "a -[RF<0 LF<0]- d\na -[RF<0 LF<0]- e\n"
        )
        overlaps = find_overlaps(model, solve_placement(model))
        assert [(o.lhs, o.rhs) for o in overlaps] == [("b", "c"), ("d", "e")]
        assert [o.volume for o in overlaps] == pytest.approx([89 * 38 * 300] * 2)

    def test_laid_out_groups_do_not_overlap(self):
        model = parse_dsl(
            "(a:2x4 =500)\n(b:2x4 =300)\n(floating:2x4 =300)\n(spare:1x4 =900)\n"
            "a -[FL<100 DF<0]- b\n"
        )
        assert find_overlaps(model, solve_placement(model)) == ()


class TestOverallBounds:
    def test_bounds_cover_every_piece(self):
        model = parse_dsl("(a:2x4 =500)\n(b:2x4 =300)\na -[FL<100 DF<0]- b\n")
        low, high = overall_bounds(model, solve_placement(model))
        assert (low.x, low.y, low.z) == (0.0, 0.0, 0.0)
        assert (high.x, high.y, high.z) == (89.0, 338.0, 500.0)

    def test_empty_model_has_empty_bounds(self):
        model = Model.of(pieces=[], connections=[])
        low, high = overall_bounds(model, solve_placement(model))
        assert low == high == Point3D(x=0.0, y=0.0, z=0.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_placement.py -q`
Expected: collection error `ImportError: cannot import name 'find_overlaps'`

- [ ] **Step 3: Write the implementation**

`solve_placement` の後ろに追加する。

```python
def find_overlaps(model: Model, placement: Placement) -> tuple[Overlap, ...]:
    """Pairs of pieces whose boxes share volume (holes and fillets ignored)."""
    boxes = [
        (piece_id, placement.poses[piece_id].bounds(piece))
        for piece_id, piece in model.pieces.items()
    ]
    overlaps = []
    for i, (lhs, (lhs_low, lhs_high)) in enumerate(boxes):
        for rhs, (rhs_low, rhs_high) in boxes[i + 1 :]:
            sizes = (
                min(lhs_high.x, rhs_high.x) - max(lhs_low.x, rhs_low.x),
                min(lhs_high.y, rhs_high.y) - max(lhs_low.y, rhs_low.y),
                min(lhs_high.z, rhs_high.z) - max(lhs_low.z, rhs_low.z),
            )
            if all(size > 0 for size in sizes):
                volume = sizes[0] * sizes[1] * sizes[2]
                if volume > TOLERANCE_MM:
                    overlaps.append(Overlap(lhs=lhs, rhs=rhs, volume=volume))
    return tuple(overlaps)


def overall_bounds(model: Model, placement: Placement) -> tuple[Point3D, Point3D]:
    """Smallest world box containing every piece."""
    if not model.pieces:
        origin = Point3D(x=0.0, y=0.0, z=0.0)
        return origin, origin
    boxes = [
        placement.poses[piece_id].bounds(piece) for piece_id, piece in model.pieces.items()
    ]
    return (
        Point3D(
            x=min(low.x for low, _ in boxes),
            y=min(low.y for low, _ in boxes),
            z=min(low.z for low, _ in boxes),
        ),
        Point3D(
            x=max(high.x for _, high in boxes),
            y=max(high.y for _, high in boxes),
            z=max(high.z for _, high in boxes),
        ),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_placement.py -q`
Expected: PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff format src/nichiyou_daiku/core/placement.py tests/core/test_placement.py
make lint && make test
git add src/nichiyou_daiku/core/placement.py tests/core/test_placement.py
git commit -m "feat(core): Detect overlapping pieces and overall bounds from placement"
```

---

### Task 4: `Assembly.placement` と移行前の照合

**Files:**
- Modify: `src/nichiyou_daiku/core/assembly/builder.py`
- Create: `tests/shell/test_placement_matches_build123d.py`（Task 6 で削除）
- Create: `tests/core/fixtures/placement_examples.json`
- Create: `tests/core/test_placement_examples.py`
- Test: `tests/core/test_assembly.py`

**Interfaces:**
- Consumes: `Placement`, `solve_placement`
- Produces: `Assembly.placement: Placement`（`Assembly.of` が設定）

- [ ] **Step 1: Write the failing test**

`tests/core/test_assembly.py` の末尾に追加する。

```python
class TestAssemblyPlacement:
    def test_assembly_carries_the_solved_placement(self):
        from nichiyou_daiku.core.model import Model
        from nichiyou_daiku.core.placement import solve_placement

        a = Piece.of(PieceType.PT_2x4, 500.0, "a")
        b = Piece.of(PieceType.PT_2x4, 300.0, "b")
        model = Model.of(
            pieces=[a, b],
            connections=[
                Connection(
                    base=BoundAnchor(
                        piece=a,
                        anchor=Anchor(contact_face="front", edge_shared_face="left", offset=FromMin(value=100)),
                    ),
                    target=BoundAnchor(
                        piece=b,
                        anchor=Anchor(contact_face="down", edge_shared_face="front", offset=FromMin(value=0)),
                    ),
                )
            ],
        )
        assert Assembly.of(model).placement == solve_placement(model)
```

Run: `uv run pytest tests/core/test_assembly.py -q -k carries`
Expected: FAIL with `AttributeError: 'Assembly' object has no attribute 'placement'`

- [ ] **Step 2: Implement**

`src/nichiyou_daiku/core/assembly/builder.py`:

```python
from ..placement import Placement, solve_placement
```

を import に追加し、`Assembly` の docstring の Attributes に `placement: World placement of every piece, solved from the connections` を追加、フィールドを追加する。

```python
    pilot_holes: dict[str, list[tuple[SurfacePoint, Hole]]]
    placement: Placement
    label: str | None
```

`Assembly.of` の `return cls(...)` に `placement=solve_placement(model),` を追加する。

Run: `uv run pytest tests/core -q`
Expected: PASS

- [ ] **Step 3: 移行前の照合テストを書く（build123d の RigidJoint 配置と比較）**

`tests/shell/test_placement_matches_build123d.py`:

```python
"""Core placement must match the RigidJoint placement it replaces.

Temporary: removed once build123d renders the core placement.
"""

import itertools
import re
from pathlib import Path

import pytest

pytest.importorskip("build123d")

from nichiyou_daiku.core.anchor import Anchor, BoundAnchor  # noqa: E402
from nichiyou_daiku.core.assembly import Assembly  # noqa: E402
from nichiyou_daiku.core.connection import Connection  # noqa: E402
from nichiyou_daiku.core.geometry import FromMax, FromMin, is_adjacent  # noqa: E402
from nichiyou_daiku.core.model import Model  # noqa: E402
from nichiyou_daiku.core.piece import Piece, PieceType  # noqa: E402
from nichiyou_daiku.dsl import parse_dsl  # noqa: E402
from nichiyou_daiku.shell.build123d_export import assembly_to_build123d  # noqa: E402

ROOT = Path(__file__).parents[2]
FACES = ["top", "down", "left", "right", "front", "back"]
ADJACENT = [(c, e) for c in FACES for e in FACES if is_adjacent(c, e)]
DOCS = [
    "prompts/system.md",
    "prompts/reference/dsl-complete.md",
    "prompts/reference/python-api.md",
    "prompts/README.md",
    "docs/dsl-specification.md",
    "docs/dsl-specification_ja.md",
    "README.md",
]


def _designs() -> list[tuple[str, str]]:
    designs = [(p.name, p.read_text()) for p in sorted((ROOT / "examples/nd_files").glob("*.nd"))]
    for doc in DOCS:
        blocks = re.findall(r"```nd\n(.*?)```", (ROOT / doc).read_text(), re.S)
        designs += [(f"{doc}#{i}", b) for i, b in enumerate(blocks) if "-[" in b]
    return designs


def _assert_same_boxes(assembly: Assembly) -> None:
    compound = assembly_to_build123d(assembly, fillet_radius=0)
    for child in compound.children:
        bb = child.bounding_box()
        low, high = assembly.placement.poses[child.label].bounds(
            assembly.model.pieces[child.label]
        )
        assert (bb.min.X, bb.min.Y, bb.min.Z, bb.max.X, bb.max.Y, bb.max.Z) == pytest.approx(
            (low.x, low.y, low.z, high.x, high.y, high.z), abs=1e-6
        ), child.label


@pytest.mark.parametrize(
    "base_faces,target_faces,offsets",
    [
        (b, t, o)
        for b, t in itertools.product(ADJACENT, ADJACENT)
        for o in ((FromMin(value=10), FromMin(value=5)), (FromMax(value=10), FromMax(value=0)))
    ],
)
def test_two_piece_placement_matches(base_faces, target_faces, offsets):
    a = Piece.of(PieceType.PT_2x4, 500.0, "a")
    b = Piece.of(PieceType.PT_2x4, 300.0, "b")
    connection = Connection(
        base=BoundAnchor(piece=a, anchor=Anchor(contact_face=base_faces[0], edge_shared_face=base_faces[1], offset=offsets[0])),
        target=BoundAnchor(piece=b, anchor=Anchor(contact_face=target_faces[0], edge_shared_face=target_faces[1], offset=offsets[1])),
    )
    _assert_same_boxes(Assembly.of(Model.of(pieces=[a, b], connections=[connection])))


@pytest.mark.parametrize("name,source", _designs(), ids=[n for n, _ in _designs()])
def test_design_placement_matches(name, source):
    assembly = Assembly.of(parse_dsl(source))
    if assembly.placement.conflicts or len(assembly.placement.groups) > 1:
        pytest.skip("RigidJoint placement is undefined for inconsistent models")
    _assert_same_boxes(assembly)
```

Run: `uv run pytest tests/shell/test_placement_matches_build123d.py -q`
Expected: PASS（1152 + 設計例。設計例のうち完全な設計 39 件以上が PASS）。1 件でも FAIL したら Task 6（shell の切り替え）に進まず原因を調べる（片方の配置規則の差を特定し、仕様の 3 規則に合わない側を直す）。

- [ ] **Step 4: 例の期待値を移行前の build123d 配置から固定する**

```bash
mkdir -p tests/core/fixtures
uv run python - <<'EOF'
import json
from pathlib import Path
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.shell.build123d_export import assembly_to_build123d

fixture = {}
for path in sorted(Path("examples/nd_files").glob("*.nd")):
    compound = assembly_to_build123d(Assembly.of(parse_dsl(path.read_text())), fillet_radius=0)
    fixture[path.name] = {
        child.label: [
            [round(child.bounding_box().min.X, 6), round(child.bounding_box().min.Y, 6), round(child.bounding_box().min.Z, 6)],
            [round(child.bounding_box().max.X, 6), round(child.bounding_box().max.Y, 6), round(child.bounding_box().max.Z, 6)],
        ]
        for child in compound.children
    }
Path("tests/core/fixtures/placement_examples.json").write_text(json.dumps(fixture, indent=1, sort_keys=True) + "\n")
print({k: len(v) for k, v in fixture.items()})
EOF
```

Expected: 4 ファイル分の部材数が表示される。

`tests/core/test_placement_examples.py`:

```python
"""Example furniture keeps the placement it had before placement moved to core."""

import json
from pathlib import Path

import pytest

from nichiyou_daiku.core.placement import solve_placement
from nichiyou_daiku.dsl import parse_dsl

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "placement_examples.json").read_text())
EXAMPLES = Path(__file__).parents[2] / "examples" / "nd_files"


@pytest.mark.parametrize("name", sorted(FIXTURE))
def test_example_keeps_its_placement(name):
    model = parse_dsl((EXAMPLES / name).read_text())
    placement = solve_placement(model)
    assert placement.conflicts == ()
    for piece_id, (low, high) in FIXTURE[name].items():
        got_low, got_high = placement.poses[piece_id].bounds(model.pieces[piece_id])
        assert (got_low.x, got_low.y, got_low.z, got_high.x, got_high.y, got_high.z) == pytest.approx(
            (*low, *high), abs=1e-6
        ), piece_id
```

Run: `uv run pytest tests/core/test_placement_examples.py -q`
Expected: PASS（4 件）

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff format src tests
make lint && make test
git add src/nichiyou_daiku/core/assembly/builder.py tests/core/test_assembly.py tests/core/fixtures/placement_examples.json tests/core/test_placement_examples.py tests/shell/test_placement_matches_build123d.py
git commit -m "feat(core): Attach solved placement to Assembly and pin example placements"
```

---

### Task 5: `validate` をコアの配置で行う

**Files:**
- Modify: `src/nichiyou_daiku/cli/utils.py`
- Modify: `src/nichiyou_daiku/cli/commands/validate.py`（全体置き換え）
- Test: `tests/cli/test_validate.py`

**Interfaces:**
- Consumes: `Assembly.placement`, `find_overlaps`, `find_joints_outside_pieces`
- Produces: `describe_placement_issues(placement: Placement) -> list[str]`（`cli/utils.py`、Task 7 も使う）

- [ ] **Step 1: Write the failing tests**

`tests/cli/test_validate.py`:
- `needs_build123d` の定義と、`@needs_build123d` デコレータをすべて削除する。`from nichiyou_daiku.shell.build123d_export import HAS_BUILD123D` も削除する。
- `test_validate_geometry_checks_can_be_skipped` を削除する。
- `test_validate_reports_contradicting_connections` の `assert "apart" in result.output` を次に置き換える。

```python
    assert "Connection b -> c: contact (z) is off by 389.0mm (loop: b -> a -> c)" in result.output
```

- 末尾に追加する。

```python
def test_validate_does_not_need_build123d(runner, tmp_path, monkeypatch):
    import nichiyou_daiku.shell.build123d_export as export_module

    monkeypatch.setattr(export_module, "HAS_BUILD123D", False)
    result = _validate(
        runner,
        tmp_path,
        """
        (a:2x4 =500)
        (b:2x4 =300)
        (c:2x4 =300)
        a -[FL<100 DF<0]- b
        a -[FL<100 DF<0]- c
        """,
    )
    assert result.exit_code == 1
    assert "Pieces 'b' and 'c' overlap (1014600.0mm³)" in result.output


def test_validate_reports_orientation_conflicts(runner, tmp_path):
    result = _validate(
        runner,
        tmp_path,
        """
        (a:2x4 =500)
        (b:2x4 =300)
        (c:2x4 =300)
        a -[RF<0 LF<0]- b
        a -[FL<100 DF<0]- c
        b -[RF<0 LF<0]- c
        """,
    )
    assert result.exit_code == 1
    assert (
        "Connection b -> c: orientation contradicts the other connections (loop: b -> a -> c)"
        in result.output
    )
```

Run: `uv run pytest tests/cli/test_validate.py -q`
Expected: FAIL — `test_validate_reports_contradicting_connections`（"off by" の文言がない）、`test_validate_does_not_need_build123d`（build123d がないと重なりを検出せず終了コード 0）、`test_validate_reports_orientation_conflicts`（回転の矛盾を報告しない）

- [ ] **Step 2: `describe_placement_issues` を追加する**

`src/nichiyou_daiku/cli/utils.py` の `TYPE_CHECKING` ブロックに `from nichiyou_daiku.core.placement import Placement` を追加し、`create_assembly_from_model` の前に追加する。

```python
def describe_placement_issues(placement: Placement) -> list[str]:
    """Human-readable lines for placement conflicts and unconnected pieces."""
    issues = []
    for conflict in placement.conflicts:
        loop = " -> ".join(conflict.loop)
        where = f"Connection {conflict.base_id} -> {conflict.target_id}"
        if conflict.kind == "rotation":
            issues.append(
                f"{where}: orientation contradicts the other connections (loop: {loop})"
            )
        else:
            issues.append(
                f"{where}: {conflict.kind} ({conflict.axis}) is off by "
                f"{abs(conflict.mismatch_mm or 0.0):.1f}mm (loop: {loop})"
            )
    if len(placement.groups) > 1:
        listed = "; ".join(", ".join(group) for group in placement.groups)
        issues.append(
            "Some pieces are not connected to each other, so their relative "
            f"position is undefined (groups: {listed})"
        )
    return issues
```

- [ ] **Step 3: `validate.py` を置き換える**

`src/nichiyou_daiku/cli/commands/validate.py` 全体:

```python
"""Validate command for DSL files."""

import sys

import click

from nichiyou_daiku.cli.utils import CliEcho, describe_placement_issues, read_dsl_file
from nichiyou_daiku.core.assembly import Assembly, find_joints_outside_pieces
from nichiyou_daiku.core.placement import find_overlaps
from nichiyou_daiku.dsl import (
    parse_dsl,
    DSLSyntaxError,
    DSLSemanticError,
    DSLValidationError,
)


def report_validation_error(
    echo: CliEcho, error_type: str, exception: Exception
) -> None:
    """Report validation error with consistent formatting.

    Args:
        echo: CliEcho instance
        error_type: Type of error (e.g., "Syntax error", "Semantic error")
        exception: The exception to report
    """
    echo.error(click.style(f"✗ {error_type}", fg="red", bold=True))
    echo.exception(f"\n{exception}")


@click.command()
@click.argument("file", type=str)
@click.pass_context
def validate(ctx: click.Context, file: str) -> None:
    """Validate a DSL file and the model it describes.

    Checks the syntax, builds the assembly and solves the placement, then
    reports contradicting connections, unconnected pieces, overlapping
    pieces and dowels that fall outside their piece.

    FILE: Path to .nd file or '-' for stdin
    """
    echo = CliEcho(ctx)

    # Read DSL content
    try:
        dsl_content = read_dsl_file(file)
    except click.ClickException as e:
        echo.error(f"Error: {e}")
        sys.exit(1)

    try:
        model = parse_dsl(dsl_content)
    except DSLSyntaxError as e:
        report_validation_error(echo, "Syntax error", e)
        sys.exit(1)
    except DSLSemanticError as e:
        report_validation_error(echo, "Semantic error", e)
        sys.exit(1)
    except DSLValidationError as e:
        report_validation_error(echo, "Validation error", e)
        sys.exit(1)
    except Exception as e:
        report_validation_error(echo, "Unexpected error", e)
        sys.exit(1)

    echo.echo(click.style("✓ DSL syntax is valid", fg="green"))
    echo.echo("\nModel summary:", verbose_only=True)
    echo.echo(f"  Pieces: {len(model.pieces)}", verbose_only=True)
    echo.echo(f"  Connections: {len(model.connections)}", verbose_only=True)
    if model.pieces:
        echo.echo("\nPieces:", verbose_only=True)
        for piece_id, piece in model.pieces.items():
            echo.echo(
                f"  - {piece_id}: {piece.type.value} @ {piece.length}mm",
                verbose_only=True,
            )

    try:
        assembly = Assembly.of(model)
    except Exception as e:
        report_validation_error(echo, "Assembly error", e)
        sys.exit(1)

    problems = [
        f"Joint {joint_id} lies outside piece "
        f"'{joint_id.rsplit('_j', 1)[0]}': the dowel layout does not fit this joint"
        for joint_id in find_joints_outside_pieces(assembly)
    ]
    problems += describe_placement_issues(assembly.placement)
    problems += [
        f"Pieces '{overlap.lhs}' and '{overlap.rhs}' overlap ({overlap.volume:.1f}mm³)"
        for overlap in find_overlaps(model, assembly.placement)
    ]

    if problems:
        echo.error(click.style("✗ Model has problems", fg="red", bold=True))
        for problem in problems:
            echo.error(f"  - {problem}")
        sys.exit(1)

    echo.echo(click.style("✓ Model is valid", fg="green"))
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/cli -q`
Expected: PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff format src tests
make lint && make test
git add src/nichiyou_daiku/cli/utils.py src/nichiyou_daiku/cli/commands/validate.py tests/cli/test_validate.py
git commit -m "refactor(cli): Validate placement in core without build123d"
```

---

### Task 6: build123d はコアの配置で描画するだけにする

**Files:**
- Modify: `src/nichiyou_daiku/shell/build123d_export.py`（全体置き換え）
- Modify: `src/nichiyou_daiku/shell/__init__.py`
- Modify: `tests/shell/test_build123d_geometry.py`, `tests/shell/test_build123d_export.py`
- Delete: `tests/shell/test_placement_matches_build123d.py`

**Interfaces:**
- Consumes: `Assembly.placement.poses[piece_id]: Pose`
- Produces: `assembly_to_build123d(assembly, fillet_radius=5.0) -> Compound`（シグネチャ不変）。`check_overlap` / `OverlapResult` / `find_joint_mismatches` は削除。

- [ ] **Step 1: 描画位置のテストを書く（リファクタリングなので今も通る）**

`tests/shell/test_build123d_geometry.py` に追加する。

```python
class TestRendersCorePlacement:
    @pytest.mark.parametrize(
        "path",
        sorted((Path(__file__).parents[2] / "examples" / "nd_files").glob("*.nd")),
        ids=lambda p: p.name,
    )
    def test_each_part_sits_where_the_placement_puts_it(self, path):
        assembly = Assembly.of(parse_dsl(path.read_text()))
        compound = assembly_to_build123d(assembly, fillet_radius=0)
        for child in compound.children:
            bb = child.bounding_box()
            low, high = assembly.placement.poses[child.label].bounds(
                assembly.model.pieces[child.label]
            )
            assert (bb.min.X, bb.min.Y, bb.min.Z, bb.max.X, bb.max.Y, bb.max.Z) == pytest.approx(
                (low.x, low.y, low.z, high.x, high.y, high.z), abs=1e-6
            )

    def test_unconnected_group_is_rendered_beside_the_rest(self):
        assembly = Assembly.of(
            parse_dsl("(a:2x4 =500)\n(b:2x4 =300)\n(floating:2x4 =300)\na -[FL<100 DF<0]- b\n")
        )
        compound = assembly_to_build123d(assembly, fillet_radius=0)
        floating = {c.label: c for c in compound.children}["floating"]
        assert floating.bounding_box().min.X == pytest.approx(189.0)
```

先頭の import に `from pathlib import Path` を追加する。

Run: `uv run pytest tests/shell/test_build123d_geometry.py -q -k RendersCore`
Expected: 例 4 件は PASS、`test_unconnected_group_is_rendered_beside_the_rest` は FAIL（現状は原点に置かれる）

- [ ] **Step 2: 旧チェックのテストを削除する**

- `tests/shell/test_build123d_geometry.py`: import から `check_overlap` を削除し、`TestCheckOverlap`・`TestJointMismatches`・`TestChecksDoNotDisturbEachOther` クラスを削除する（同等の検証は `tests/core/test_placement.py` の `TestOverlaps` と矛盾テストにある）。
- `tests/shell/test_build123d_export.py`: `test_check_overlap_requires_build123d` を削除し、未使用になる `from unittest.mock import Mock` を削除する。
- `git rm tests/shell/test_placement_matches_build123d.py`

- [ ] **Step 3: `build123d_export.py` を置き換える**

`src/nichiyou_daiku/shell/build123d_export.py` 全体:

```python
"""Export nichiyou-daiku assemblies to build123d format for 3D visualization.

This module renders an Assembly with build123d: each piece becomes a solid
(filleted, with its pilot holes) placed where the assembly's placement puts it.
"""

from typing import TYPE_CHECKING

import numpy as np

from nichiyou_daiku.core.assembly import (
    Assembly,
    Hole as NichiyouHole,
)
from nichiyou_daiku.core.geometry import (
    Point3D,
    SurfacePoint,
    Box as NichiyouBox,
)
from nichiyou_daiku.core.placement import Pose

# Check if build123d is available
HAS_BUILD123D = False
try:
    from build123d import (
        Box,
        Compound,
        Part,
        Location,
        Plane,
        Align,
        fillet,
        Axis,
        Cylinder,
    )

    HAS_BUILD123D = True
except ImportError:
    pass

if TYPE_CHECKING:
    from build123d import (
        Box,
        Compound,
        Part,
        Location,
        Plane,
        Align,
        fillet,
        Axis,
        Cylinder,
    )


def _as_tuple(point: Point3D) -> tuple[float, float, float]:
    """Convert a Point3D to a tuple of floats.

    Args:
        point: The point to convert

    Returns:
        Tuple of (x, y, z) coordinates as floats
    """
    return (float(point.x), float(point.y), float(point.z))


def _create_hole(
    position: SurfacePoint,
    hole: NichiyouHole,
    box: NichiyouBox,
) -> "Part":
    """Create a cylinder for hole subtraction at the specified position.

    Args:
        position: The hole center on the face it is drilled into
        hole: The hole specification (diameter and depth)
        box: The box containing dimension information

    Returns:
        A build123d Part (cylinder) positioned and oriented for subtraction
    """
    face = position.face
    point = Point3D.of(box, position)

    # Face rotation angles to orient cylinder inward (Z-axis aligned with hole direction)
    face_rotations: dict[str, tuple[float, float, float]] = {
        "left": (0, 90, 0),  # cylinder Z -> +X (inward)
        "right": (0, -90, 0),  # cylinder Z -> -X (inward)
        "back": (-90, 0, 0),  # cylinder Z -> +Y (inward)
        "front": (90, 0, 0),  # cylinder Z -> -Y (inward)
        "down": (0, 0, 0),  # cylinder Z -> +Z (inward)
        "top": (180, 0, 0),  # cylinder Z -> -Z (inward)
    }

    # Calculate depth: use specified depth or fixed value for through-holes
    depth = hole.depth if hole.depth is not None else 100.0

    # Create cylinder centered at origin, then rotate and translate
    cylinder = Cylinder(
        radius=hole.diameter / 2,
        height=depth,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )

    rotation = face_rotations[face]
    return cylinder.locate(Location(_as_tuple(point), rotation))


def _create_piece_from(
    id: str,
    box: NichiyouBox,
    fillet_radius: float,
    pilot_holes: list[tuple[SurfacePoint, NichiyouHole]] | None = None,
) -> "Part":
    """Create a build123d Part from a nichiyou Box.

    Args:
        id: The piece ID
        box: The nichiyou Box to convert
        fillet_radius: Radius for edge fillets in mm (default: 5.0)
        pilot_holes: List of (position, hole) tuples for pilot holes

    Returns:
        A build123d Part with filleted edges and pilot holes
    """
    piece = (
        Box(
            length=float(box.shape.width),
            width=float(box.shape.height),
            height=float(box.shape.length),
            align=Align.MIN,
        )
        + Part()
    )

    # Round the four long edges (the piece's length runs along Z). Two fillets
    # meeting across the thickness would fail, so keep the radius below half
    # of the smaller cross-section side.
    radius = min(fillet_radius, min(box.shape.width, box.shape.height) / 2 * 0.99)
    if 0 < radius:
        piece = Part(fillet(piece.edges().filter_by(Axis.Z), radius=radius).wrapped)

    # Subtract pilot holes after fillet
    if pilot_holes:
        for position, hole in pilot_holes:
            hole_cylinder = _create_hole(position, hole, box)
            piece = piece - hole_cylinder

    piece.label = id
    return piece  # type: ignore


def _location_of(pose: Pose) -> "Location":
    rotation = np.array(pose.rotation, dtype=float)
    return Location(
        Plane(
            origin=pose.translation,
            x_dir=tuple(rotation[:, 0]),
            z_dir=tuple(rotation[:, 2]),
        )
    )


def assembly_to_build123d(
    assembly: Assembly,
    fillet_radius: float = 5.0,
) -> "Compound":
    """Convert a nichiyou Assembly to a build123d Compound.

    Creates a build123d Part for each piece and places it where the
    assembly's placement puts it.

    Args:
        assembly: The nichiyou Assembly to convert
        fillet_radius: Radius for edge fillets in mm (default: 5.0, use 0 to disable)

    Returns:
        A build123d Compound containing all placed parts

    Raises:
        ImportError: If build123d is not installed

    Example:
        >>> from nichiyou_daiku.core.model import Model
        >>> from nichiyou_daiku.core.assembly import Assembly
        >>> model = Model.of(pieces=[], connections=[])
        >>> assembly = Assembly.of(model)
        >>> compound = assembly_to_build123d(assembly, fillet_radius=3.0)
    """
    if not HAS_BUILD123D:
        raise ImportError(
            "build123d is required for 3D visualization. "
            "Please install it with: pip install nichiyou-daiku[viz]"
        )

    parts = []
    for piece_id, box in assembly.boxes.items():
        part = _create_piece_from(
            piece_id,
            box,
            fillet_radius,
            pilot_holes=assembly.pilot_holes.get(piece_id),
        )
        parts.append(part.locate(_location_of(assembly.placement.poses[piece_id])))

    return Compound(label=assembly.label or "assembly", children=parts)
```

`src/nichiyou_daiku/shell/__init__.py` の末尾ブロックを次に置き換える。

```python
# build123d_export imports build123d lazily, so it is always importable;
# only advertise its functions when build123d is installed.
from .build123d_export import HAS_BUILD123D

if HAS_BUILD123D:
    from .build123d_export import assembly_to_build123d  # noqa: F401

    __all__.append("assembly_to_build123d")
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/shell tests/core tests/cli tests/regression -q`
Expected: PASS（`TestRendersCorePlacement` 5 件を含む。`validate` は Task 5 でコアに移っているので旧関数を使っていない）

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff format src tests
make lint && make test
git add -A src/nichiyou_daiku/shell tests/shell
git commit -m "refactor(shell): Render the core placement instead of chaining RigidJoints"
```

---

### Task 7: 警告して続行・レポートの外形寸法

**Files:**
- Modify: `src/nichiyou_daiku/cli/utils.py`
- Modify: `src/nichiyou_daiku/shell/resources.py`
- Modify: `src/nichiyou_daiku/shell/report_generator.py`
- Create: `tests/cli/test_placement_warnings.py`
- Test: `tests/shell/test_resources.py`, `tests/shell/test_report_generator.py`

**Interfaces:**
- Consumes: `describe_placement_issues`, `overall_bounds`, `Assembly.placement`
- Produces: `warn_placement_issues(assembly: Assembly, echo: CliEcho) -> None`; `ResourceSummary.overall_size: tuple[float, float, float] | None`, `ResourceSummary.size_reference: str | None`

- [ ] **Step 1: Write the failing tests**

`tests/cli/test_placement_warnings.py`:

```python
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
        cli, ["export", str(_write(tmp_path, CONTRADICTING)), "-f", "step", "-o", str(output)]
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
```

`tests/shell/test_resources.py` の末尾に追加する。

```python
class TestOverallSize:
    def test_single_group_reports_its_size(self):
        from nichiyou_daiku.core.assembly import Assembly
        from nichiyou_daiku.dsl import parse_dsl
        from nichiyou_daiku.shell.resources import extract_resources

        summary = extract_resources(
            Assembly.of(parse_dsl("(a:2x4 =500)\n(b:2x4 =300)\na -[FL<100 DF<0]- b\n"))
        )
        assert summary.overall_size == (89.0, 338.0, 500.0)
        assert summary.size_reference == "a"

    def test_unconnected_groups_report_no_size(self):
        from nichiyou_daiku.core.assembly import Assembly
        from nichiyou_daiku.dsl import parse_dsl
        from nichiyou_daiku.shell.resources import extract_resources

        summary = extract_resources(Assembly.of(parse_dsl("(a:2x4 =500)\n(b:2x4 =300)\n")))
        assert summary.overall_size is None
        assert summary.size_reference is None
```

Run: `uv run pytest tests/cli/test_placement_warnings.py tests/shell/test_resources.py -q`
Expected: FAIL（警告が出ない、`overall_size` 属性がない）

- [ ] **Step 2: `warn_placement_issues` を追加し、`create_assembly_from_model` から呼ぶ**

`src/nichiyou_daiku/cli/utils.py` の `describe_placement_issues` の後ろに追加する。

```python
def warn_placement_issues(assembly: Assembly, echo: CliEcho) -> None:
    """Warn on stderr about placement issues; the command carries on."""
    for issue in describe_placement_issues(assembly.placement):
        echo.info(click.style(f"Warning: {issue}", fg="yellow"))
```

`create_assembly_from_model` の `return Assembly.of(model)` を次に置き換える。

```python
        assembly = Assembly.of(model)
    except Exception as e:
        echo.exception(f"Error creating assembly: {e}")
        sys.exit(1)
    warn_placement_issues(assembly, echo)
    return assembly
```

（元の `except` ブロックは上に移したので削除する。）

- [ ] **Step 3: 外形寸法を `ResourceSummary` とレポートに追加する**

`src/nichiyou_daiku/shell/resources.py`:
- import に `from nichiyou_daiku.core.placement import overall_bounds` を追加する。
- `ResourceSummary` に追加し、docstring の Attributes に説明を加える。

```python
    overall_size: tuple[float, float, float] | None = None
    size_reference: str | None = None
```

（Attributes: `overall_size: World X × Y × Z extent in mm when all pieces are connected`, `size_reference: Piece whose length runs along Z (the placement's first piece)`）

- `extract_resources` の `return ResourceSummary(` の前に追加し、引数に `overall_size=overall_size, size_reference=size_reference,` を加える。

```python
    overall_size = None
    size_reference = None
    if len(assembly.placement.groups) == 1:
        low, high = overall_bounds(assembly.model, assembly.placement)
        overall_size = (
            round(high.x - low.x, 6),
            round(high.y - low.y, 6),
            round(high.z - low.z, 6),
        )
        size_reference = assembly.placement.groups[0][0]
```

`src/nichiyou_daiku/shell/report_generator.py` の `_generate_overview_section` で、`return f"""...` の前に次を追加し、`## Project Overview` の直後の行に `{size_line}` を挿入する（`- **Total Pieces**` の前）。

```python
    size_line = ""
    if summary.overall_size is not None:
        x, y, z = summary.overall_size
        size_line = (
            f"- **Overall Size (X × Y × Z)**: {_mm(x)} × {_mm(y)} × {_mm(z)} mm "
            f"(Z is the length direction of '{summary.size_reference}')\n"
        )
```

結果の該当部分:

```python
## Project Overview

{size_line}- **Total Pieces**: {summary.total_pieces}
```

`tests/shell/test_report_generator.py` の末尾に追加する。

```python
class TestOverviewSize:
    def test_overview_shows_overall_size_when_known(self):
        summary = ResourceSummary(
            pieces=[_piece("a", 500.0)],
            total_pieces=1,
            pieces_by_type={PieceType.PT_2x4: 1},
            total_length_by_type={PieceType.PT_2x4: 500.0},
            total_volume=0.0,
            overall_size=(89.0, 38.0, 500.5),
            size_reference="a",
        )
        overview = _generate_overview_section(summary, "P")
        assert "- **Overall Size (X × Y × Z)**: 89 × 38 × 500.5 mm" in overview

    def test_overview_omits_size_when_unknown(self):
        summary = ResourceSummary(
            pieces=[_piece("a", 500.0)],
            total_pieces=1,
            pieces_by_type={PieceType.PT_2x4: 1},
            total_length_by_type={PieceType.PT_2x4: 500.0},
            total_volume=0.0,
        )
        assert "Overall Size" not in _generate_overview_section(summary, "P")
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/cli tests/shell -q`
Expected: PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff format src tests
make lint && make test
git add src/nichiyou_daiku/cli/utils.py src/nichiyou_daiku/shell/resources.py src/nichiyou_daiku/shell/report_generator.py tests/cli/test_placement_warnings.py tests/shell/test_resources.py tests/shell/test_report_generator.py
git commit -m "feat(cli): Warn about placement issues and report the overall size"
```

---

### Task 8: ドキュメントと最終確認

**Files:**
- Modify: `README.md`, `docs/api-specification.md`, `docs/api-specification_ja.md`
- Modify (local only, not committed): `CLAUDE.md`

- [ ] **Step 1: 古い記述を探す**

```bash
grep -rn "check_overlap\|find_joint_mismatches\|no-geometry\|RigidJoint\|connect_to" README.md docs prompts CLAUDE.md | grep -v "docs/superpowers"
grep -rn "validate" README.md docs/api-specification.md docs/api-specification_ja.md | head -20
```

Expected: ヒットした箇所を Step 2 で直す。

- [ ] **Step 2: 記述を更新する**

- `README.md` の「DSL CLI Tools」のコードブロックで、`validate` と `report` の 2 項目を次に置き換え、ブロック直後（`See the \`examples/nd_files/\` directory ...` の前）に 1 文を追加する。

```bash
# Validate the model: syntax, contradicting connections, unconnected or
# overlapping pieces, and dowels outside their piece (no build123d needed)
nichiyou-daiku validate furniture.nd

# Generate markdown report (the overview includes the overall size X × Y × Z)
nichiyou-daiku report furniture.nd -o report.md
```

```markdown
Commands other than `validate` print a warning and carry on when connections contradict each other or some pieces are not connected.
```
- `docs/api-specification.md` / `_ja.md` の Assembly の節に `placement: Placement` を追加し、新しい節「Placement」を追加する（`Pose`、`Placement`、`Conflict`、`Overlap`、`solve_placement`、`find_overlaps`、`overall_bounds` のシグネチャと 1 行説明。英語版は英語、日本語版は日本語）。例:

```python
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.placement import find_overlaps
from nichiyou_daiku.dsl import parse_dsl

model = parse_dsl("(a:2x4 =500)\n(b:2x4 =300)\na -[FL<100 DF<0]- b\n")
assembly = Assembly.of(model)
print(assembly.placement.poses["b"].bounds(model.pieces["b"]))
print(assembly.placement.conflicts, find_overlaps(model, assembly.placement))
```

- `CLAUDE.md`（ローカル）: 「検証の厳格化…（2026年10月）」の項の `validate` の行を「配置はコア（`core/placement.py`）で解く。validate は build123d 不要」に直し、`--no-geometry` の記述を削除する。プロジェクト構造の `core/` に `placement.py # 部材配置ソルバー` を追加し、`shell/build123d_export.py` のコメントを「3D化（コアの配置で描画）」にする。

- [ ] **Step 3: ドキュメントの例を検証する**

```bash
uv run python - <<'EOF'
import re
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.dsl import parse_dsl
for f in ["README.md", "docs/api-specification.md", "docs/api-specification_ja.md"]:
    for block in re.findall(r"```python\n(.*?)```", open(f).read(), re.S):
        if "placement" in block:
            exec(block, {})
print("placement examples OK")
EOF
for f in examples/nd_files/*.nd; do uv run nichiyou-daiku validate "$f" | tail -1; done
```

Expected: `placement examples OK`、各例で `✓ Model is valid`

- [ ] **Step 4: 最終確認**

Run: `make ci-local`
Expected: `✅ All CI checks passed!`

- [ ] **Step 5: Commit**

```bash
git add README.md docs/api-specification.md docs/api-specification_ja.md
git commit -m "docs: Document core placement, validate checks and overall size"
```
