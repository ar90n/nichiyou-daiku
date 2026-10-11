# 留め具配置の作り直し Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ダボ・ビスを「2 つの部材の接触面の重なり」の中に 1 つのルールで並べ、置けない場合は報告する。旧来の接合（Joint）系のコードは削除する。

**Architecture:** `core/assembly/fasteners.py` の `layout_fasteners(connection)` が、接続自身の相対配置（`core/placement.relative_pose`）から base 座標系での接触面の長方形を求め、短辺中央・長辺 1/4 と 3/4（狭ければ中央 1 本）に留め具を置く。
`Assembly` は `fasteners` / `fastener_issues` を持ち、`pilot_holes` はそこから作る。CLI は `describe_assembly_issues` で配置と留め具の問題をまとめて報告する。

**Tech Stack:** Python 3.13, pydantic（frozen モデル）, numpy, pytest, hypothesis, Click

**Spec:** `docs/superpowers/specs/2026-10-11-fastener-layout-design.md`

## Global Constraints

- 新しい依存を追加しない。データクラスは frozen な pydantic モデル。
- ルール: d = 留め具の直径（ダボは `2 * radius`、ビスは `diameter`）。接触面の短辺 S・長辺 L（等しいときは軸番号の小さい方 i を L とする）。
  `S < 2d` は `LayoutIssue`。短辺方向は中央。長辺方向は `L/2 >= 2d` なら始点から `L/4` と `3L/4`、そうでなければ `L/2`。
- 接触面の長さが `1e-6` mm 以下なら `LayoutIssue(message="pieces do not share a contact area")`。
- 狭すぎる場合のメッセージは `f"contact area {S:.1f} x {L:.1f}mm is too narrow for a {d:.1f}mm {kind} (needs {2*d:.1f}mm)"`。
- 穴: ダボは両側 `Hole(diameter=2r, depth=length/2)`。ビスは target `Hole(diameter)`（貫通）、base `Hole(diameter, depth=length − target の接触面法線方向の厚み)`。
- `validate` は留め具の問題を終了コード 1 で報告。他コマンドは `Warning: Connection a -> b: <message>` を出して続行。
- 互換レイヤーは置かない（`Assembly.joints` / `joint_conns` / `find_joints_outside_pieces` / `Joint` / `JointPair` / `project_joint` / `Orientation` / `Orientation3D` / `Vector2D` / `anchor.as_orientation` を削除）。
- Conventional Commits、件名大文字始まり。ドットファイルはコミットしない。各タスクのコミット前に `make lint` と `make test`（カバレッジ 90% 以上）。最終タスクで `make ci-local`。

## Review Focus

1. 部材が辺でしか接していない接続（例: `FT<0 DF<0` で相手が外にはみ出す）でも落ちずに報告になること → Task 2 `test_edge_only_contact_is_reported`
2. 1x4 の木口のような狭い接触面で、直径がぎりぎり入る／入らない境界（19mm に φ8 / φ10） → Task 2 `test_dowel_fits_a_1x4_edge` / `test_too_narrow_contact_is_reported`
3. 正方形の接触面（L と S が等しい）で 1 本が中央に置かれ、結果が決定的なこと → Task 2 `test_square_contact_gets_a_single_centred_dowel`
4. 以前 `NotImplementedError` だった面の組み合わせで留め具が置けること → Task 2 `test_every_face_combination_lays_out_without_errors`、Task 3 `test_former_not_implemented_face_combination_now_lays_out`
5. 留め具が置けないモデルで `export` / `report` が落ちずに警告して続行すること → Task 3 `test_report_warns_about_fasteners_that_do_not_fit`

---

## File Structure

| ファイル | 役割 | 変更 |
|---|---|---|
| `src/nichiyou_daiku/core/geometry/coordinates.py` | `SurfacePoint.from_point` 追加、`Vector2D` / `Orientation` / `Orientation3D` 削除 | 変更（Task 1, 4） |
| `src/nichiyou_daiku/core/placement.py` | `relative_pose(base, target) -> Pose` 追加 | 変更（Task 2） |
| `src/nichiyou_daiku/core/assembly/models.py` | `Hole`, `Fastener`, `LayoutIssue`, `FastenerKind`（`Joint` / `JointPair` は Task 4 で削除） | 変更（Task 2, 4） |
| `src/nichiyou_daiku/core/assembly/fasteners.py` | `layout_fasteners` | 新規（Task 2） |
| `src/nichiyou_daiku/core/assembly/builder.py` | `Assembly`（`fasteners` / `fastener_issues`、`pilot_holes` 生成） | 全面置き換え（Task 3） |
| `src/nichiyou_daiku/core/assembly/__init__.py` | 公開名 | 変更（Task 3, 4） |
| `src/nichiyou_daiku/core/assembly/{joints,projection,constants}.py` | 削除 | Task 4 |
| `src/nichiyou_daiku/core/anchor.py` | `as_orientation` 削除 | Task 4 |
| `src/nichiyou_daiku/cli/utils.py`, `cli/commands/validate.py` | `describe_assembly_issues` / `warn_assembly_issues` | 変更（Task 3） |
| `tests/core/test_fasteners.py` | 留め具配置の単体・プロパティテスト | 新規（Task 2） |
| `tests/core/test_assembly.py` | 全面書き直し | Task 3 |
| `tests/cli/test_validate.py`, `tests/cli/test_placement_warnings.py` | CLI | 変更（Task 3） |
| `tests/core/test_geometry.py` | `from_point` テスト追加、Orientation3D テスト削除 | 変更（Task 1, 4） |
| `tests/core/test_{projection,orientation,orientation_preservation,orientation_transform}.py` | 削除 | Task 4 |
| docs / prompts | 留め具ルールと API | 変更（Task 5） |

---

### Task 1: `SurfacePoint.from_point`

**Files:**
- Modify: `src/nichiyou_daiku/core/geometry/coordinates.py`（`SurfacePoint.of`）
- Test: `tests/core/test_geometry.py`

**Interfaces:**
- Produces: `SurfacePoint.from_point(box: Box, face: Face, point: Point3D) -> SurfacePoint`（`Point3D.of(box, surface_point)` の逆）

- [ ] **Step 1: Write the failing test**

`tests/core/test_geometry.py` の末尾に追加する。

```python
class TestSurfacePointFromPoint:
    @pytest.mark.parametrize("face", ["top", "down", "left", "right", "front", "back"])
    @pytest.mark.parametrize("u,v", [(0.0, 0.0), (10.5, -7.25), (-30.0, 12.0)])
    def test_round_trips_through_point3d(self, face, u, v):
        from nichiyou_daiku.core.geometry import Box, Point2D, Point3D, SurfacePoint

        box = Box(shape=Shape3D(width=89.0, height=38.0, length=500.0))
        surface_point = SurfacePoint(face=face, position=Point2D(u=u, v=v))
        back = SurfacePoint.from_point(box, face, Point3D.of(box, surface_point))
        assert back.face == face
        assert (back.position.u, back.position.v) == pytest.approx((u, v))
```

（`Shape3D` は既存の import にある。）

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_geometry.py -q -k FromPoint`
Expected: FAIL with `AttributeError: type object 'SurfacePoint' has no attribute 'from_point'`

- [ ] **Step 3: Implement**

`SurfacePoint.of` の本体のうち、`# Convert EdgePoint to Point3D using standard logic` から `return cls(face=face, position=Point2D(u=u, v=v))` までを次に置き換え、その直後に `from_point` を追加する。

```python
        return cls.from_point(box, face, Point3D._of_edge_point(box, edge_point))

    @classmethod
    def from_point(cls, box: Box, face: Face, point: "Point3D") -> "SurfacePoint":
        """Express a point lying on ``face`` in that face's 2D coordinates.

        Inverse of ``Point3D.of(box, surface_point)``.

        Args:
            box: The piece's box
            face: The face the point lies on
            point: The point in the piece's local coordinates

        Returns:
            SurfacePoint with 2D coordinates centred on the face
        """
        # Face frames are right-handed (u x v = outward normal), centred on the face:
        # - top:   u=+X, v=+Y
        # - down:  u=-X, v=+Y
        # - left:  u=-Y, v=+Z
        # - right: u=+Y, v=+Z
        # - front: u=-X, v=+Z
        # - back:  u=+X, v=+Z
        width, height, length = box.shape.width, box.shape.height, box.shape.length
        if face == "top":
            u, v = point.x - width / 2, point.y - height / 2
        elif face == "down":
            u, v = width / 2 - point.x, point.y - height / 2
        elif face == "left":
            u, v = height / 2 - point.y, point.z - length / 2
        elif face == "right":
            u, v = point.y - height / 2, point.z - length / 2
        elif face == "front":
            u, v = width / 2 - point.x, point.z - length / 2
        elif face == "back":
            u, v = point.x - width / 2, point.z - length / 2
        else:
            raise ValueError(f"Invalid face: {face}")
        return cls(face=face, position=Point2D(u=u, v=v))
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/core -q`
Expected: PASS（`SurfacePoint.of` の既存テストも含む）

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff format src tests
make lint && make test
git add src/nichiyou_daiku/core/geometry/coordinates.py tests/core/test_geometry.py
git commit -m "feat(core): Express a 3D point in a face's surface coordinates"
```

---

### Task 2: 留め具の配置 `layout_fasteners`

**Files:**
- Modify: `src/nichiyou_daiku/core/placement.py`
- Modify: `src/nichiyou_daiku/core/assembly/models.py`
- Create: `src/nichiyou_daiku/core/assembly/fasteners.py`
- Test: `tests/core/test_fasteners.py`

**Interfaces:**
- Consumes: `SurfacePoint.from_point`（Task 1）、`relative_rotation`, `Pose`（core/placement）
- Produces:
  - `relative_pose(base: BoundAnchor, target: BoundAnchor) -> Pose`（core/placement。target 座標 → base 座標）
  - `FastenerKind = Literal["dowel", "screw"]`, `Fastener`, `LayoutIssue`（core/assembly/models）
  - `layout_fasteners(connection: Connection) -> tuple[tuple[Fastener, ...], LayoutIssue | None]`（core/assembly/fasteners）

- [ ] **Step 1: Write the failing tests**

`tests/core/test_fasteners.py`:

```python
"""Tests for laying out dowels and screws in the contact area."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.assembly.fasteners import layout_fasteners
from nichiyou_daiku.core.assembly.models import Hole
from nichiyou_daiku.core.connection import (
    Connection,
    DowelConnection,
    ScrewConnection,
    _get_dimension_for_face,
)
from nichiyou_daiku.core.geometry import (
    Box,
    Edge,
    FromMax,
    FromMin,
    Point3D,
    edge_length_of,
    is_adjacent,
)
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
from nichiyou_daiku.core.placement import solve_placement
from nichiyou_daiku.dsl import parse_dsl

FACES = ["top", "down", "left", "right", "front", "back"]
ADJACENT = [(c, e) for c in FACES for e in FACES if is_adjacent(c, e)]
TYPES = [PieceType.PT_2x4, PieceType.PT_1x4]


def _layout(source: str):
    connection = next(iter(parse_dsl(source).connections.values()))
    fasteners, issue = layout_fasteners(connection)
    return connection, fasteners, issue


def _xyz(point: Point3D) -> np.ndarray:
    return np.array([point.x, point.y, point.z])


def _base_point(connection: Connection, fastener) -> tuple[float, float, float]:
    point = Point3D.of(Box(shape=get_shape(connection.base.piece)), fastener.base_position)
    return (round(point.x, 6), round(point.y, 6), round(point.z, 6))


class TestLayoutFasteners:
    def test_vanilla_connection_has_no_fasteners(self):
        _, fasteners, issue = _layout("(a:2x4 =500)\n(b:2x4 =300)\na -[FL<100 DF<0]- b\n")
        assert fasteners == ()
        assert issue is None

    def test_dowels_in_a_t_joint(self):
        connection, fasteners, issue = _layout(
            "(leg:2x4 =700)\n(apron:2x4 =500)\nleg -[FL<100 DF<0 D(4, 30)]- apron\n"
        )
        assert issue is None
        assert [_base_point(connection, f) for f in fasteners] == [
            (19.0, 38.0, 33.25),
            (19.0, 38.0, 77.75),
        ]
        assert {f.base_position.face for f in fasteners} == {"front"}
        assert {f.target_position.face for f in fasteners} == {"down"}
        assert {f.base_hole for f in fasteners} == {Hole(diameter=8.0, depth=15.0)}
        assert {f.target_hole for f in fasteners} == {Hole(diameter=8.0, depth=15.0)}
        assert {(f.base_id, f.target_id, f.kind) for f in fasteners} == {
            ("leg", "apron", "dowel")
        }

    def test_dowel_fits_a_1x4_edge(self):
        connection, fasteners, issue = _layout(
            "(a:2x4 =500)\n(b:1x4 =300)\na -[FL<100 DF<0 D(4, 30)]- b\n"
        )
        assert issue is None
        assert [_base_point(connection, f) for f in fasteners] == [
            (9.5, 38.0, 33.25),
            (9.5, 38.0, 77.75),
        ]

    def test_too_narrow_contact_is_reported(self):
        _, fasteners, issue = _layout(
            "(a:2x4 =500)\n(b:1x4 =300)\na -[FL<100 DF<0 D(5, 30)]- b\n"
        )
        assert fasteners == ()
        assert issue is not None
        assert (issue.base_id, issue.target_id, issue.kind) == ("a", "b", "dowel")
        assert issue.message == (
            "contact area 19.0 x 89.0mm is too narrow for a 10.0mm dowel (needs 20.0mm)"
        )

    def test_square_contact_gets_a_single_centred_dowel(self):
        connection, fasteners, issue = _layout(
            "(a:2x4 =500)\n(b:2x4 =300)\na -[LF<100 TL<0 D(5, 30)]- b\n"
        )
        assert issue is None
        assert [_base_point(connection, f) for f in fasteners] == [(0.0, 19.0, 81.0)]

    def test_edge_only_contact_is_reported(self):
        _, fasteners, issue = _layout(
            "(a:2x4 =500)\n(b:2x4 =300)\na -[FT<0 DF<0 D(4, 30)]- b\n"
        )
        assert fasteners == ()
        assert issue is not None
        assert issue.message == "pieces do not share a contact area"

    def test_screws_pass_through_the_target_into_the_base(self):
        _, fasteners, issue = _layout(
            "(base:2x4 =500)\n(target:1x4 =300)\nbase -[FL<100 BL<0 S(Slim:3.3x25)]- target\n"
        )
        assert issue is None
        assert len(fasteners) == 2
        assert {f.target_hole for f in fasteners} == {Hole(diameter=3.3)}
        assert {f.base_hole for f in fasteners} == {Hole(diameter=3.3, depth=6.0)}
        assert {f.kind for f in fasteners} == {"screw"}

    @pytest.mark.parametrize("base_faces", ADJACENT)
    @pytest.mark.parametrize("target_faces", ADJACENT)
    def test_every_face_combination_lays_out_without_errors(self, base_faces, target_faces):
        base = Piece.of(PieceType.PT_2x4, 500.0, "base")
        target = Piece.of(PieceType.PT_2x4, 300.0, "target")
        base_length = edge_length_of(Box(shape=get_shape(base)), Edge(lhs=base_faces[0], rhs=base_faces[1]))
        target_length = edge_length_of(Box(shape=get_shape(target)), Edge(lhs=target_faces[0], rhs=target_faces[1]))
        connection = Connection(
            base=BoundAnchor(
                piece=base,
                anchor=Anchor(contact_face=base_faces[0], edge_shared_face=base_faces[1], offset=FromMin(value=base_length * 0.3)),
            ),
            target=BoundAnchor(
                piece=target,
                anchor=Anchor(contact_face=target_faces[0], edge_shared_face=target_faces[1], offset=FromMax(value=target_length * 0.2)),
            ),
            type=DowelConnection(radius=3.0, depth=12.0),
        )
        fasteners, issue = layout_fasteners(connection)
        assert (len(fasteners) in (1, 2)) != (issue is not None)


@st.composite
def fastened_connections(draw) -> Connection:
    base = Piece.of(draw(st.sampled_from(TYPES)), draw(st.floats(100, 1000)), "base")
    target = Piece.of(draw(st.sampled_from(TYPES)), draw(st.floats(100, 1000)), "target")
    kind = draw(st.sampled_from(["dowel", "screw"]))
    base_faces = draw(st.sampled_from(ADJACENT))
    target_faces = draw(
        st.sampled_from([f for f in ADJACENT if kind == "dowel" or f[0] in ("front", "back")])
    )

    def anchor(piece: Piece, faces) -> Anchor:
        length = edge_length_of(Box(shape=get_shape(piece)), Edge(lhs=faces[0], rhs=faces[1]))
        value = draw(st.floats(min_value=0, max_value=length, allow_nan=False))
        offset = draw(st.sampled_from([FromMin, FromMax]))(value=value)
        return Anchor(contact_face=faces[0], edge_shared_face=faces[1], offset=offset)

    if kind == "dowel":
        connection_type = DowelConnection(radius=draw(st.floats(2.0, 5.0)), depth=10.0)
    else:
        target_thickness = _get_dimension_for_face(get_shape(target), target_faces[0])
        base_depth = _get_dimension_for_face(get_shape(base), base_faces[0])
        connection_type = ScrewConnection(
            diameter=draw(st.floats(2.0, 5.0)),
            length=target_thickness + draw(st.floats(1.0, min(base_depth, 30.0))),
        )
    return Connection(
        base=BoundAnchor(piece=base, anchor=anchor(base, base_faces)),
        target=BoundAnchor(piece=target, anchor=anchor(target, target_faces)),
        type=connection_type,
    )


@given(fastened_connections())
@settings(max_examples=300, deadline=None)
def test_fasteners_sit_inside_the_shared_contact_area(connection):
    fasteners, issue = layout_fasteners(connection)
    base, target = connection.base.piece, connection.target.piece
    placement = solve_placement(Model.of(pieces=[base, target], connections=[connection]))
    base_low, base_high = placement.poses["base"].bounds(base)
    target_low, target_high = placement.poses["target"].bounds(target)
    low = np.maximum(_xyz(base_low), _xyz(target_low))
    high = np.minimum(_xyz(base_high), _xyz(target_high))
    sizes = high - low
    plane_axis = int(np.argmin(np.abs(sizes)))
    in_plane = [axis for axis in range(3) if axis != plane_axis]
    shortest = min(sizes[axis] for axis in in_plane)
    match connection.type:
        case DowelConnection(radius=radius):
            diameter = radius * 2
        case ScrewConnection(diameter=screw_diameter):
            diameter = screw_diameter

    if issue is not None:
        assert fasteners == ()
        assert shortest <= 1e-6 or shortest < 2 * diameter
        return

    assert shortest >= 2 * diameter - 1e-9
    assert len(fasteners) in (1, 2)
    points = []
    for fastener in fasteners:
        on_base = _xyz(placement.poses["base"].apply(Point3D.of(Box(shape=get_shape(base)), fastener.base_position)))
        on_target = _xyz(placement.poses["target"].apply(Point3D.of(Box(shape=get_shape(target)), fastener.target_position)))
        assert on_base == pytest.approx(on_target, abs=1e-6)
        for axis in in_plane:
            assert low[axis] + diameter - 1e-6 <= on_base[axis] <= high[axis] - diameter + 1e-6
        points.append(on_base)
    if len(points) == 2:
        assert np.linalg.norm(points[0] - points[1]) >= 2 * diameter - 1e-6
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_fasteners.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'nichiyou_daiku.core.assembly.fasteners'`

- [ ] **Step 3: Implement**

`src/nichiyou_daiku/core/placement.py` の `relative_rotation` の後ろに追加する。

```python
def relative_pose(base: BoundAnchor, target: BoundAnchor) -> Pose:
    """Pose of the target in the base's local coordinates for one connection."""
    rotation = relative_rotation(base, target)
    translation = _anchor_point(base) - rotation @ _anchor_point(target)
    return Pose(
        rotation=(
            (int(rotation[0, 0]), int(rotation[0, 1]), int(rotation[0, 2])),
            (int(rotation[1, 0]), int(rotation[1, 1]), int(rotation[1, 2])),
            (int(rotation[2, 0]), int(rotation[2, 1]), int(rotation[2, 2])),
        ),
        translation=(float(translation[0]), float(translation[1]), float(translation[2])),
    )
```

（`_anchor_point` は同じモジュールで後に定義されているが、呼び出し時に解決されるので問題ない。）

`src/nichiyou_daiku/core/assembly/models.py`: import に `from typing import Literal` を追加し、`Hole` の後ろに追加する。

```python
FastenerKind = Literal["dowel", "screw"]


class Fastener(BaseModel, frozen=True):
    """A dowel or screw joining two pieces, with the hole it needs in each.

    Attributes:
        base_id: ID of the connection's base piece
        target_id: ID of the connection's target piece (one connection per pair)
        kind: "dowel" or "screw"
        base_position: Where it enters the base, on the base's contact face
        target_position: Where it enters the target, on the target's contact face
        base_hole: Hole drilled into the base
        target_hole: Hole drilled into the target
    """

    base_id: str
    target_id: str
    kind: FastenerKind
    base_position: SurfacePoint
    target_position: SurfacePoint
    base_hole: Hole
    target_hole: Hole


class LayoutIssue(BaseModel, frozen=True):
    """A connection whose fasteners could not be laid out."""

    base_id: str
    target_id: str
    kind: FastenerKind
    message: str
```

`src/nichiyou_daiku/core/assembly/fasteners.py`:

```python
"""Lay out dowels and screws inside the area where two pieces touch.

Each connection is laid out from its own relative placement, so the result
does not depend on the rest of the model. Fasteners go across the middle of
the contact rectangle's short side and at 1/4 and 3/4 of its long side (one
in the middle when there is no room for two).
"""

import numpy as np

from ..connection import (
    Connection,
    DowelConnection,
    ScrewConnection,
    _get_dimension_for_face,
)
from ..geometry import Box, Point3D, SurfacePoint, Vector3D
from ..piece import get_shape
from ..placement import relative_pose
from .models import Fastener, FastenerKind, Hole, LayoutIssue

CONTACT_TOLERANCE_MM = 1e-6


def _positions_along(start: float, length: float, diameter: float) -> list[float]:
    if length / 2 >= 2 * diameter:
        return [start + length / 4, start + 3 * length / 4]
    return [start + length / 2]


def _surface_point(box: Box, face, point: np.ndarray) -> SurfacePoint:
    return SurfacePoint.from_point(
        box, face, Point3D(x=float(point[0]), y=float(point[1]), z=float(point[2]))
    )


def layout_fasteners(
    connection: Connection,
) -> tuple[tuple[Fastener, ...], LayoutIssue | None]:
    """Fasteners for one connection, or the reason they do not fit."""
    kind: FastenerKind
    match connection.type:
        case DowelConnection(radius=radius, depth=length):
            kind = "dowel"
            diameter = radius * 2
            base_hole = target_hole = Hole(diameter=diameter, depth=length / 2)
        case ScrewConnection(diameter=diameter, length=length):
            kind = "screw"
            target_thickness = _get_dimension_for_face(
                get_shape(connection.target.piece), connection.target.anchor.contact_face
            )
            target_hole = Hole(diameter=diameter)
            base_hole = Hole(diameter=diameter, depth=length - target_thickness)
        case _:
            return (), None

    base, target = connection.base, connection.target
    base_shape = get_shape(base.piece)
    base_high = np.array([base_shape.width, base_shape.height, base_shape.length])
    relative = relative_pose(base, target)
    target_low, target_high = relative.bounds(target.piece)
    low = np.maximum(np.zeros(3), [target_low.x, target_low.y, target_low.z])
    high = np.minimum(base_high, [target_high.x, target_high.y, target_high.z])

    normal_vector = Vector3D.normal_of(base.anchor.contact_face)
    normal = np.array([normal_vector.x, normal_vector.y, normal_vector.z])
    plane_axis = int(np.argmax(np.abs(normal)))
    plane = base_high[plane_axis] if normal[plane_axis] > 0 else 0.0
    first, second = (axis for axis in range(3) if axis != plane_axis)
    first_size, second_size = high[first] - low[first], high[second] - low[second]

    def issue(message: str) -> LayoutIssue:
        return LayoutIssue(
            base_id=base.piece.id, target_id=target.piece.id, kind=kind, message=message
        )

    if min(first_size, second_size) <= CONTACT_TOLERANCE_MM:
        return (), issue("pieces do not share a contact area")
    long_axis, short_axis = (first, second) if first_size >= second_size else (second, first)
    long_size, short_size = high[long_axis] - low[long_axis], high[short_axis] - low[short_axis]
    if short_size < 2 * diameter:
        return (), issue(
            f"contact area {short_size:.1f} x {long_size:.1f}mm is too narrow "
            f"for a {diameter:.1f}mm {kind} (needs {2 * diameter:.1f}mm)"
        )

    base_box = Box(shape=base_shape)
    target_box = Box(shape=get_shape(target.piece))
    to_target = relative.rotation_matrix().T
    shift = np.array(relative.translation)
    fasteners = []
    for along in _positions_along(low[long_axis], long_size, diameter):
        point = np.zeros(3)
        point[plane_axis] = plane
        point[long_axis] = along
        point[short_axis] = low[short_axis] + short_size / 2
        fasteners.append(
            Fastener(
                base_id=base.piece.id,
                target_id=target.piece.id,
                kind=kind,
                base_position=_surface_point(base_box, base.anchor.contact_face, point),
                target_position=_surface_point(
                    target_box, target.anchor.contact_face, to_target @ (point - shift)
                ),
                base_hole=base_hole,
                target_hole=target_hole,
            )
        )
    return tuple(fasteners), None
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/core/test_fasteners.py -q`
Expected: PASS（7 + 576 + 1 件）

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff format src tests
make lint && make test
git add src/nichiyou_daiku/core/placement.py src/nichiyou_daiku/core/assembly/models.py src/nichiyou_daiku/core/assembly/fasteners.py tests/core/test_fasteners.py
git commit -m "feat(core): Lay out dowels and screws in the shared contact area"
```

---

### Task 3: Assembly と CLI を留め具に切り替える

**Files:**
- Modify: `src/nichiyou_daiku/core/assembly/builder.py`（全体置き換え）
- Modify: `src/nichiyou_daiku/core/assembly/__init__.py`
- Modify: `src/nichiyou_daiku/cli/utils.py`, `src/nichiyou_daiku/cli/commands/validate.py`
- Test: `tests/core/test_assembly.py`（全体置き換え）, `tests/cli/test_validate.py`, `tests/cli/test_placement_warnings.py`

**Interfaces:**
- Consumes: `layout_fasteners`, `Fastener`, `LayoutIssue`（Task 2）
- Produces: `Assembly.fasteners: tuple[Fastener, ...]`, `Assembly.fastener_issues: tuple[LayoutIssue, ...]`;
  `describe_assembly_issues(assembly: Assembly) -> list[str]`, `warn_assembly_issues(assembly: Assembly, echo: CliEcho) -> None`（cli/utils）。
  `Assembly.joints` / `joint_conns` / `find_joints_outside_pieces` / `describe_placement_issues` / `warn_placement_issues` は削除。

- [ ] **Step 1: Write the failing tests**

`tests/core/test_assembly.py` 全体:

```python
"""Tests for assembly module."""

from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.assembly import Assembly, Hole
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.geometry import Box, FromMin
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
from nichiyou_daiku.core.placement import solve_placement
from nichiyou_daiku.dsl import parse_dsl

T_JOINT = "(leg:2x4 =700)\n(apron:2x4 =500)\nleg -[FL<100 DF<0 {kind}]- apron\n"


def _assembly(source: str) -> Assembly:
    return Assembly.of(parse_dsl(source))


class TestBox:
    def test_should_handle_different_piece_lengths(self):
        for length in [500.0, 1000.0, 2000.0]:
            box = Box(shape=get_shape(Piece.of(PieceType.PT_2x4, length)))
            assert (box.shape.width, box.shape.height, box.shape.length) == (89.0, 38.0, length)


class TestFastenersAndHoles:
    def test_vanilla_connection_has_no_fasteners_or_holes(self):
        assembly = _assembly(T_JOINT.format(kind="V"))
        assert assembly.fasteners == ()
        assert assembly.fastener_issues == ()
        assert assembly.pilot_holes == {}

    def test_dowels_drill_matching_holes_in_both_pieces(self):
        assembly = _assembly(T_JOINT.format(kind="D(4, 30)"))
        assert len(assembly.fasteners) == 2
        for piece_id, face in (("leg", "front"), ("apron", "down")):
            holes = assembly.pilot_holes[piece_id]
            assert [hole for _, hole in holes] == [Hole(diameter=8.0, depth=15.0)] * 2
            assert {position.face for position, _ in holes} == {face}

    def test_screws_pass_through_the_target_into_the_base(self):
        assembly = _assembly(
            "(base:2x4 =500)\n(target:1x4 =300)\nbase -[FL<100 BL<0 S(Slim:3.3x25)]- target\n"
        )
        assert [hole for _, hole in assembly.pilot_holes["target"]] == [Hole(diameter=3.3)] * 2
        assert [hole for _, hole in assembly.pilot_holes["base"]] == [
            Hole(diameter=3.3, depth=6.0)
        ] * 2

    def test_fastener_that_does_not_fit_is_reported_not_drilled(self):
        assembly = _assembly("(a:2x4 =500)\n(b:1x4 =300)\na -[FL<100 DF<0 D(5, 30)]- b\n")
        assert assembly.fasteners == ()
        assert assembly.pilot_holes == {}
        (issue,) = assembly.fastener_issues
        assert (issue.base_id, issue.target_id, issue.kind) == ("a", "b", "dowel")
        assert "too narrow" in issue.message

    def test_former_not_implemented_face_combination_now_lays_out(self):
        # front/back to front/back with left edges used to raise NotImplementedError
        assembly = _assembly("(a:2x4 =500)\n(b:2x4 =500)\na -[FL<100 BL<100 D(4, 30)]- b\n")
        assert len(assembly.fasteners) == 2
        assert assembly.fastener_issues == ()


class TestAssemblyPlacement:
    def test_assembly_carries_the_solved_placement(self):
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

`tests/cli/test_validate.py`:
- `test_validate_reports_assembly_errors` を次に置き換える。

```python
def test_validate_accepts_dowels_on_formerly_unsupported_faces(runner, tmp_path):
    # front/back to front/back with left edges used to fail with NotImplementedError
    result = _validate(
        runner,
        tmp_path,
        """
        (a:2x4 =500)
        (b:2x4 =500)
        a -[FL<100 BL<100 D(4, 30)]- b
        """,
    )
    assert result.exit_code == 0
    assert "✓ Model is valid" in result.output
```

- `test_validate_reports_dowels_outside_the_piece` を次に置き換える。

```python
def test_validate_reports_fasteners_that_do_not_fit(runner, tmp_path):
    result = _validate(
        runner,
        tmp_path,
        """
        (a:2x4 =500)
        (b:1x4 =300)
        a -[FL<100 DF<0 D(5, 30)]- b
        """,
    )
    assert result.exit_code == 1
    assert (
        "Connection a -> b: contact area 19.0 x 89.0mm is too narrow for a 10.0mm dowel"
        in result.output
    )
```

- `test_validate_debug_prints_traceback_for_assembly_errors` を次に置き換える（以前の入力はもう失敗しない）。

```python
def test_validate_debug_prints_traceback_for_assembly_errors(runner, tmp_path, monkeypatch):
    import nichiyou_daiku.cli.commands.validate as validate_module

    def broken(model):
        raise RuntimeError("boom")

    monkeypatch.setattr(validate_module.Assembly, "of", broken)
    dsl_file = tmp_path / "design.nd"
    dsl_file.write_text("(a:2x4 =500)\n(b:2x4 =300)\na -[FL<100 DF<0]- b\n")
    result = runner.invoke(cli, ["-d", "validate", str(dsl_file)])
    assert result.exit_code == 1
    assert "✗ Assembly error" in result.output
    assert "Traceback" in result.output
```

`tests/cli/test_placement_warnings.py` の末尾に追加する。

```python
def test_report_warns_about_fasteners_that_do_not_fit(runner, tmp_path):
    source = "(a:2x4 =500)\n(b:1x4 =300)\na -[FL<100 DF<0 D(5, 30)]- b\n"
    result = runner.invoke(cli, ["report", str(_write(tmp_path, source))])
    assert result.exit_code == 0
    assert "Warning: Connection a -> b: contact area 19.0 x 89.0mm is too narrow" in result.output
```

Run: `uv run pytest tests/core/test_assembly.py tests/cli -q`
Expected: FAIL（`Assembly` に `fasteners` がない、留め具の問題が報告されない、など）

- [ ] **Step 2: `builder.py` を置き換える**

`src/nichiyou_daiku/core/assembly/builder.py` 全体:

```python
"""Assembly builder for creating 3D assemblies from models.

This module contains the Assembly class that turns a Model into placed
pieces with their fasteners and pilot holes.
"""

from pydantic import BaseModel

from ..geometry import Box, SurfacePoint
from ..model import Model
from ..piece import get_shape
from ..placement import Placement, solve_placement
from .fasteners import layout_fasteners
from .models import Fastener, Hole, LayoutIssue


class Assembly(BaseModel, frozen=True):
    """Complete 3D assembly: placed pieces, fasteners and pilot holes.

    Attributes:
        model: The source model with piece and connection definitions
        boxes: Dictionary mapping piece IDs to their 3D boxes
        fasteners: Dowels and screws laid out in each connection's contact area
        fastener_issues: Connections whose fasteners could not be laid out
        pilot_holes: Dictionary mapping piece IDs to lists of (SurfacePoint, Hole)
            tuples; the SurfacePoint names the face the hole is drilled into
        placement: World placement of every piece, solved from the connections
        label: Optional label for the assembly

    Examples:
        >>> from nichiyou_daiku.dsl import parse_dsl
        >>> assembly = Assembly.of(
        ...     parse_dsl("(a:2x4 =500)\\n(b:2x4 =300)\\na -[FL<100 DF<0 D(4, 30)]- b\\n")
        ... )
        >>> len(assembly.fasteners)
        2
        >>> [hole.diameter for _, hole in assembly.pilot_holes["a"]]
        [8.0, 8.0]
    """

    model: Model
    boxes: dict[str, Box]
    fasteners: tuple[Fastener, ...]
    fastener_issues: tuple[LayoutIssue, ...]
    pilot_holes: dict[str, list[tuple[SurfacePoint, Hole]]]
    placement: Placement
    label: str | None

    @classmethod
    def of(cls, model: Model) -> "Assembly":
        """Create an Assembly from a Model.

        Args:
            model: Model containing pieces and connections

        Returns:
            Assembly with placement, fasteners and pilot holes
        """
        boxes = {
            piece.id: Box(shape=get_shape(piece)) for piece in model.pieces.values()
        }

        fasteners: list[Fastener] = []
        issues: list[LayoutIssue] = []
        for connection in model.connections.values():
            laid_out, issue = layout_fasteners(connection)
            fasteners.extend(laid_out)
            if issue is not None:
                issues.append(issue)

        pilot_holes: dict[str, list[tuple[SurfacePoint, Hole]]] = {}
        for fastener in fasteners:
            pilot_holes.setdefault(fastener.base_id, []).append(
                (fastener.base_position, fastener.base_hole)
            )
            pilot_holes.setdefault(fastener.target_id, []).append(
                (fastener.target_position, fastener.target_hole)
            )

        return cls(
            model=model,
            label=model.label,
            boxes=boxes,
            fasteners=tuple(fasteners),
            fastener_issues=tuple(issues),
            pilot_holes=pilot_holes,
            placement=solve_placement(model),
        )
```

`src/nichiyou_daiku/core/assembly/__init__.py`: `from .builder import Assembly, find_joints_outside_pieces` を
`from .builder import Assembly` に、`from .models import Hole, Joint, JointPair` を
`from .models import Fastener, FastenerKind, Hole, Joint, JointPair, LayoutIssue` にし、
`from .fasteners import layout_fasteners` を追加する。`__all__` から `"find_joints_outside_pieces"` を削除し、
`"Fastener"`, `"FastenerKind"`, `"LayoutIssue"`, `"layout_fasteners"` を追加する。docstring の Public API の
`find_joints_outside_pieces` の行を `- Fastener / LayoutIssue / layout_fasteners: Dowels and screws in the contact area` に置き換える。

- [ ] **Step 3: CLI を切り替える**

`src/nichiyou_daiku/cli/utils.py`:
- `describe_placement_issues` を次の `describe_assembly_issues` に置き換える（`TYPE_CHECKING` の `Placement` の import は不要になるので削除）。

```python
def describe_assembly_issues(assembly: Assembly) -> list[str]:
    """Human-readable lines for placement conflicts, unconnected pieces and
    fasteners that do not fit."""
    placement = assembly.placement
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
                f"{format_mm(abs(conflict.mismatch_mm or 0.0))}mm (loop: {loop})"
            )
    if len(placement.groups) > 1:
        listed = "; ".join(", ".join(group) for group in placement.groups)
        issues.append(
            "Some pieces are not connected to each other, so their relative "
            f"position is undefined (groups: {listed})"
        )
    issues += [
        f"Connection {issue.base_id} -> {issue.target_id}: {issue.message}"
        for issue in assembly.fastener_issues
    ]
    return issues
```

- `warn_placement_issues` を次に置き換え、`create_assembly_from_model` の呼び出しも `warn_assembly_issues(assembly, echo)` にする。

```python
def warn_assembly_issues(assembly: Assembly, echo: CliEcho) -> None:
    """Warn on stderr about placement and fastener issues; the command carries on."""
    for issue in describe_assembly_issues(assembly):
        echo.info(click.style(f"Warning: {issue}", fg="yellow"))
```

`src/nichiyou_daiku/cli/commands/validate.py`:
- import を `from nichiyou_daiku.cli.utils import (CliEcho, describe_assembly_issues, format_mm, read_dsl_file)` と
  `from nichiyou_daiku.core.assembly import Assembly` に変える（`find_joints_outside_pieces` を削除）。
- `problems = [...find_joints_outside_pieces...]` と `problems += describe_placement_issues(assembly.placement)` の 2 文を次に置き換える。

```python
    problems = describe_assembly_issues(assembly)
```

- docstring の "and dowels that fall outside their piece" を "and fasteners that do not fit their joint" にする。

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/core tests/cli tests/shell src --doctest-modules -q`
Expected: PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff format src tests
make lint && make test
git add src/nichiyou_daiku/core/assembly/builder.py src/nichiyou_daiku/core/assembly/__init__.py src/nichiyou_daiku/cli/utils.py src/nichiyou_daiku/cli/commands/validate.py tests/core/test_assembly.py tests/cli/test_validate.py tests/cli/test_placement_warnings.py
git commit -m "refactor(core): Build pilot holes from fasteners laid out in the contact area"
```

---

### Task 4: 使われなくなった接合のコードを削除する

**Files:**
- Delete: `src/nichiyou_daiku/core/assembly/joints.py`, `projection.py`, `constants.py`
- Delete: `tests/core/test_projection.py`, `tests/core/test_orientation.py`, `tests/core/test_orientation_preservation.py`, `tests/core/test_orientation_transform.py`
- Modify: `src/nichiyou_daiku/core/assembly/models.py`, `src/nichiyou_daiku/core/assembly/__init__.py`
- Modify: `src/nichiyou_daiku/core/geometry/coordinates.py`, `src/nichiyou_daiku/core/geometry/__init__.py`, `src/nichiyou_daiku/core/anchor.py`
- Modify: `tests/core/test_geometry.py`

**Interfaces:**
- Produces: 削除のみ。`core.assembly` の公開名は `Assembly`, `Fastener`, `FastenerKind`, `Hole`, `LayoutIssue`, `layout_fasteners`。

- [ ] **Step 1: 削除前に、削除対象を参照しているものを確認する**

Run:

```bash
grep -rnE "Orientation3D|\bOrientation\b|Vector2D|as_orientation|JointPair|\bJoint\b|project_joint|joint_conns|\.joints\b|find_joints_outside_pieces" src tests examples --include='*.py' | grep -v "core/assembly/joints.py\|core/assembly/projection.py\|tests/core/test_projection.py\|tests/core/test_orientation"
```

Expected: `core/assembly/models.py`, `core/assembly/__init__.py`, `core/geometry/coordinates.py`, `core/geometry/__init__.py`,
`core/anchor.py`, `tests/core/test_geometry.py` と、examples のコメント中の "T-Joint" 等の語だけ（コードの参照はない）。
ほかの参照が出た場合は、そのファイルも Step 2 で同様に直す。

- [ ] **Step 2: 削除する**

```bash
git rm -q src/nichiyou_daiku/core/assembly/joints.py src/nichiyou_daiku/core/assembly/projection.py src/nichiyou_daiku/core/assembly/constants.py
git rm -q tests/core/test_projection.py tests/core/test_orientation.py tests/core/test_orientation_preservation.py tests/core/test_orientation_transform.py
```

- `core/assembly/models.py`: `class Joint` と `class JointPair` を削除し、それらだけが使っていた import
  （`BoundAnchor`, `as_surface_point`, `Face`, `Orientation3D`, `Vector3D`, `cross`, `opposite`）を削除する。モジュールの docstring を
  "Data models for fasteners and the holes they need." にする。
- `core/assembly/__init__.py`: `Joint`, `JointPair`, `project_joint` の import・`__all__`・docstring の行を削除する。
- `core/geometry/coordinates.py`: `class Vector2D`（`class SurfacePoint` の直前まで）と、`class Orientation` から
  ファイル末尾まで（`Orientation` と `Orientation3D`）を削除する。使われなくなった `cast` と `field_validator` を import から削除する。
  `math` が `Vector3D` の doctest でしか使われなくなった場合は、モジュールの `import math` を削除し、doctest 側に `>>> import math` を加える。
- `core/geometry/__init__.py`: `Vector2D`, `Orientation3D`, `Orientation` の import と `__all__` の項目を削除する。
- `core/anchor.py`: `as_orientation` 関数と、import の `Orientation`（と、それだけが使っていた `opposite as opposite_face`）を削除する。
- `tests/core/test_geometry.py`: `TestOrientation3DFromEuler` と `TestOrientation3DOrthogonalization` クラスを削除する。

- [ ] **Step 3: 参照が残っていないことを確認する**

Run: 同じ grep（Step 1）
Expected: examples のコメント中の語だけ。

Run: `uv run ruff check src tests && uv run pyright src/nichiyou_daiku`
Expected: エラーなし（未使用 import が出たら削除する）

- [ ] **Step 4: Run tests**

Run: `make test`
Expected: PASS、カバレッジ 90% 以上

- [ ] **Step 5: Commit**

```bash
uv run ruff format src tests
make lint
git add -A src/nichiyou_daiku tests
git commit -m "refactor(core): Remove joint and orientation code replaced by fastener layout"
```

---

### Task 5: ドキュメントと最終確認

**Files:**
- Modify: `docs/api-specification.md`, `docs/api-specification_ja.md`, `docs/dsl-specification.md`, `docs/dsl-specification_ja.md`,
  `prompts/reference/dsl-complete.md`, `prompts/reference/python-api.md`, `prompts/system.md`
- Modify (local only): `CLAUDE.md`

- [ ] **Step 1: 古い記述を探す**

```bash
grep -rnE "joint_conns|\.joints\b|JointPair|class Joint|Orientation3D|find_joints_outside|25\.4|dowel.*(place|layout|position)" docs/api-specification*.md docs/dsl-specification*.md prompts README.md CLAUDE.md | grep -v "docs/superpowers"
```

- [ ] **Step 2: 記述を更新する**

- `docs/api-specification.md`: `Assembly` のクラス一覧の `joints` / `joint_conns` の 2 行を次に置き換え、Example の
  `len(assembly.joints)` / `len(assembly.joint_conns)` の 4 行を `len(assembly.fasteners)` の例に置き換える。

```python
    fasteners: tuple[Fastener, ...]           # Dowels and screws, laid out in each contact area
    fastener_issues: tuple[LayoutIssue, ...]  # Connections whose fasteners do not fit
```

```python
>>> len(assembly.fasteners)  # a vanilla connection has no fasteners
0
```

  「Pilot holes:」の段落の後ろに、次の段落と、その下に Python のコードブロック（`class Fastener` / `class LayoutIssue` の定義）を追加する。

段落:

```markdown
**Fasteners:** dowels and screws are laid out inside the rectangle where the two contact faces overlap: across the middle of its short side, and at 1/4 and 3/4 of its long side (one in the middle when the long side is shorter than 4 × diameter). A contact area narrower than 2 × diameter, or pieces that only touch along an edge, give a `LayoutIssue` instead of fasteners; `validate` reports it and other commands warn and carry on.
```

コードブロックの中身:

```python
class Fastener(BaseModel, frozen=True):
    base_id: str
    target_id: str
    kind: Literal["dowel", "screw"]
    base_position: SurfacePoint    # on the base's contact face
    target_position: SurfacePoint  # on the target's contact face
    base_hole: Hole
    target_hole: Hole

class LayoutIssue(BaseModel, frozen=True):
    base_id: str
    target_id: str
    kind: Literal["dowel", "screw"]
    message: str
```

- `docs/api-specification_ja.md`: 同じ箇所を日本語で更新する（クラス一覧のコメントは「各接触面に並べたダボ・ビス」「留め具が入らない接続」、段落は
  「**留め具:** ダボとビスは、2 つの接触面が重なる長方形の中に並べる。短辺方向は中央、長辺方向は 1/4 と 3/4 の位置（長辺が直径の 4 倍未満なら中央に 1 本）。
  重なりの短辺が直径の 2 倍未満、または部材が辺でしか接していない場合は留め具を作らず `LayoutIssue` になる。`validate` はこれを報告し、ほかのコマンドは警告して続行する。」）。
- `prompts/reference/python-api.md`: `joints: dict[str, Joint]` と `joint_conns` の 2 行を英語版 api-specification と同じ 2 行に置き換え、
  ツリーの `# Assembly (3D placement, joints, pilot holes)` を `# Assembly (placement, fasteners, pilot holes)` にする。
- `docs/dsl-specification.md` の「Dowel Connection (D)」節の箇条書きの最後と、`prompts/reference/dsl-complete.md` の Dowel の説明の後ろに追加する。

```markdown
- Dowels (and screws) are placed inside the area where the two contact faces overlap: centred across its short side, at 1/4 and 3/4 of its long side (one in the middle if the long side is under 4 × diameter). If the short side is under 2 × diameter the connection gets no fasteners and `validate` reports it.
```

  `docs/dsl-specification_ja.md` の同じ節には日本語で追加する: 「ダボ（とビス）は 2 つの接触面が重なる範囲の中に置く。短辺方向は中央、長辺方向は 1/4 と 3/4 の位置（長辺が直径の 4 倍未満なら中央に 1 本）。短辺が直径の 2 倍未満なら留め具は作られず、`validate` が報告する。」
- `prompts/system.md` のダボの説明（`D(` の記法を説明している箇所）の直後に、英語版と同じ 1 行を追加する。
- `CLAUDE.md`（ローカル）: 「検証の厳格化…（2026年10月）」の項の「既知の制約: ダボ配置は…」の行を
  「ダボ・ビスは接触面の重なりの中に自動配置（2 本なら 1/4・3/4、狭ければ 1 本、入らなければ報告）」に置き換え、プロジェクト構造の `assembly/` の説明を「組み立て（配置・留め具・下穴）」にする。

- [ ] **Step 3: ドキュメントの例とサンプルを検証する**

```bash
uv run python - <<'EOF'
import re
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.dsl import parse_dsl
issues = 0
for f in ["prompts/system.md", "prompts/reference/dsl-complete.md", "prompts/reference/python-api.md",
          "prompts/README.md", "docs/dsl-specification.md", "docs/dsl-specification_ja.md", "README.md"]:
    for block in re.findall(r"`{3}nd\n(.*?)`{3}", open(f).read(), re.S):
        if "-[" in block:
            issues += len(Assembly.of(parse_dsl(block)).fastener_issues)
print("fastener issues in docs:", issues)
EOF
for f in examples/nd_files/*.nd; do uv run nichiyou-daiku validate "$f" | tail -1; done
```

Expected: `fastener issues in docs: 0`、各例で `✓ Model is valid`

- [ ] **Step 4: 最終確認**

Run: `make ci-local`
Expected: `✅ All CI checks passed!`

- [ ] **Step 5: Commit**

```bash
git add docs/api-specification.md docs/api-specification_ja.md docs/dsl-specification.md docs/dsl-specification_ja.md prompts/reference/dsl-complete.md prompts/reference/python-api.md prompts/system.md
git commit -m "docs: Describe fastener layout and the new Assembly fields"
```
