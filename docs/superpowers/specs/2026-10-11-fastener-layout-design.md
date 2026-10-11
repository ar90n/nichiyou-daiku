# 留め具配置の作り直し（Fastener Layout）設計

- 日付: 2026-10-11
- ステータス: 実装済み（ブランチ refactor/joint-layout）
- 対象: リファクタリング・サブプロジェクト M2-3（接合の作り直し）
- 前提: M2-1「部材配置のコア移行」（`docs/superpowers/specs/2026-10-11-core-placement-design.md`）の上に作る

## 背景

M2-1 で部材の配置はコア（`core/placement.py`）が接続のアンカーから直接解くようになった。その結果、
`core/assembly` の接合（`Joint` / `JointPair`、`joints.py`、`projection.py`）は下穴の位置を出すためだけの仕組みになっている。
この仕組みは面の組み合わせごとの場合分けと固定オフセット（中心から ±25.4mm 等）でダボを置くため、

- 一部の面・辺の組み合わせで `NotImplementedError` になる
- 多くの組み合わせでダボ（と穴）が部材の外にはみ出す（現在は `validate` が `find_joints_outside_pieces` で検出するだけ）
- 同じ向きの計算が複数箇所に重複している

## 目的

ダボ・ビスを「2 つの部材の接触面が実際に重なっている長方形」の中に、面の組み合わせに依存しない 1 つのルールで並べる。
置けない場合は配置の矛盾と同様に報告する。

## 合意した方針（決定事項と理由）

1. **接触面の重なりの中に留め具を並べる。** 必ず両方の部材の中に入り、場合分けが不要になるため。
2. **接続ごとに、その接続自身の相対配置から計算する（案 A）。** 全体の配置やほかの接続との矛盾に左右されず、
   その接合部としての正しい穴位置が出るため。
3. **本数と並べ方は自動ルール。** 本数を DSL で指定する機能は M2-4 で検討する。
4. **置けない場合は報告する。** `validate` はエラー（終了コード 1）、`export` / `report` / `view` / `drawing` は警告して
   その接続の留め具を省いて続行する（M2-1 の配置の矛盾と同じ扱い）。
5. **1 ペア複数接続は作らない。** 直方体どうしは 1 平面でしか接しないため、同じペアの 2 つ目の接続は重複か矛盾にしかならない。
   もともとの動機（天板を前後の幕板の両方に留められない）は別ペアの問題で、M2-1 のソルバーで解消済み。
6. **接合 ID の型付けはやめる。** 接合（`Joint`）自体がなくなり、留め具は 1 ペア 1 接続なので `(base_id, target_id)` で特定できる。

## スコープ外

- 留め具の本数・位置を DSL で指定する機能（M2-4）
- 1 接続に複数種類の留め具を混在させる機能
- `coordinates.py` / `report_generator.py` の分割（M2-2。本変更で使われなくなるコードの削除は本スコープに含む）

## 設計

### 1. データモデル（`src/nichiyou_daiku/core/assembly/models.py`）

```python
FastenerKind = Literal["dowel", "screw"]

class Fastener(BaseModel, frozen=True):
    base_id: str
    target_id: str                  # 1 ペア 1 接続なので base_id と target_id で接続が決まる
    kind: FastenerKind
    base_position: SurfacePoint     # base の接触面上の位置
    target_position: SurfacePoint   # target の接触面上の位置
    base_hole: Hole
    target_hole: Hole

class LayoutIssue(BaseModel, frozen=True):
    base_id: str
    target_id: str
    kind: FastenerKind
    message: str
```

`Hole` は既存のまま（`diameter`, `depth: float | None`）。

`Assembly`（`builder.py`）:

- 削除: `joints`, `joint_conns`
- 追加: `fasteners: tuple[Fastener, ...]`, `fastener_issues: tuple[LayoutIssue, ...]`
- `pilot_holes: dict[str, list[tuple[SurfacePoint, Hole]]]` は形を変えず、`fasteners` から作る
  （各留め具の base 側 `(base_position, base_hole)` を base に、target 側を target に追加）。

### 2. 並べ方（`src/nichiyou_daiku/core/assembly/fasteners.py`）

`layout_fasteners(connection: Connection) -> tuple[tuple[Fastener, ...], LayoutIssue | None]`
（`VanillaConnection` は `((), None)`）。

1. **相対位置**: target 座標系 → base 座標系の変換
   `relative = Pose(rotation=relative_rotation(base, target), translation=p_A − R_rel·p_B)`
   （`p_A`, `p_B` はアンカー点。`core/placement.py` と同じ式）。
2. **接触面の長方形**: base の箱 `[0, W] × [0, H] × [0, L]` と `relative.bounds(target_piece)` を比べる。
   base の接触面の法線の軸 k では 2 つの箱はちょうど接している（厚み 0）。残りの 2 軸 i < j（軸番号順）の区間の重なり
   `[max(lo), min(hi)]` が接触面の長方形。どちらかの長さが `1e-6` mm 以下なら
   `LayoutIssue(message="pieces do not share a contact area")`。
3. **ルール**（d = 留め具の直径。ダボは `2 * radius`、ビスは `diameter`）:
   - 長方形の短い辺を S、長い辺を L とする。等しい場合は軸番号の小さい方（i）を L とする。
   - `S < 2d` なら `LayoutIssue(message=f"contact area {S:.1f} x {L:.1f}mm is too narrow for a {d:.1f}mm {kind} (needs {2d:.1f}mm)")`。
     この接続の留め具は作らない。
   - 短い辺の方向は中央。長い辺の方向は `L/2 >= 2d` なら区間の始点から `L/4` と `3L/4` の 2 本、そうでなければ `L/2` の 1 本。
4. **穴の位置**: 各点（base 座標系、接触面上）を base の接触面上の `SurfacePoint` にする。target 側は
   `R_rel^T · (p − t)` で target 座標系へ移し、target の接触面上の `SurfacePoint` にする。
   3D 点 → `SurfacePoint` の変換は新設する `SurfacePoint.from_point(box, face, point)`（`Point3D.of(box, SurfacePoint)` の逆）。
5. **穴の寸法**（現行と同じ）:
   - ダボ: base・target とも `Hole(diameter=2r, depth=length/2)`
   - ビス: target は `Hole(diameter, depth=None)`（貫通）、base は `Hole(diameter, depth=length − target の接触面法線方向の厚み)`

保証: 留め具は必ず両部材の接触面の重なりの中にあり、端から d 以上離れる。結果は面の組み合わせ・全体の配置・他の接続との矛盾に依存しない。

### 3. 利用側

- `Assembly.of`: 接続ごとに `layout_fasteners` を呼び、`fasteners` / `fastener_issues` / `pilot_holes` を作る。
- CLI:
  - `cli/utils.describe_placement_issues(placement)` を `describe_assembly_issues(assembly)` に置き換え、留め具の問題を
    `Connection {base_id} -> {target_id}: {message}` の形で配置の問題に続けて出す。
  - `warn_placement_issues` を `warn_assembly_issues` に改名（挙動は同じ: `Warning: ...` を標準エラーへ、続行）。
  - `validate`: `find_joints_outside_pieces` の報告を削除し、`describe_assembly_issues` の結果を問題として報告する（終了コード 1）。
- `report` / build123d: `pilot_holes` を使い続けるので変更なし（留め具の位置の値だけが変わる）。

### 4. 削除するもの

- `core/assembly/joints.py`, `core/assembly/projection.py`, `core/assembly/constants.py`
- `Joint`, `JointPair`, `project_joint`, `find_joints_outside_pieces`
- `Orientation`, `Orientation3D`, `Vector2D`（`core/geometry`）、`anchor.as_orientation`
- 上記のテスト（`tests/core/test_projection.py`, `test_orientation*.py` など該当部分）
- `core/assembly/__init__.py` / `core/geometry/__init__.py` の公開名、examples/ と docs/ の参照

### 5. ドキュメント

- `docs/api-specification.md` / `_ja.md`: `Assembly` のフィールド、`Fastener` / `LayoutIssue`。削除した API の記述を消す。
- `docs/dsl-specification.md` / `_ja.md`、`prompts/reference/dsl-complete.md`、`prompts/system.md`:
  ダボ・ビスの並べ方（接触面の重なりの中、2 本なら 1/4 の位置、狭ければ 1 本、入らなければ報告）。

## テストと移行

### 移行手順

1. `SurfacePoint.from_point` を追加（往復テスト）。
2. `fasteners.py` と `Fastener` / `LayoutIssue` を追加（Assembly は未変更）。
3. Assembly を切り替える（`fasteners` / `fastener_issues` 追加、`pilot_holes` を新方式で生成、`joints` / `joint_conns` 削除）。
4. CLI を切り替える（`describe_assembly_issues`、`validate`、警告）。
5. 使われなくなったコードとテストを削除する。
6. ドキュメントを更新し、`make ci-local` を通す。

### テスト

- 期待値を固定する例:
  - `(leg:2x4 =700)(apron:2x4 =500) leg -[FL<100 DF<0 D(4, 30)]- apron`: 接触面 38 × 89mm、ダボ 2 本。
    base（leg）座標で x = 19、z = 33.25 と 77.75（y = 38 の front 面上）。穴は両側とも φ8 × 15。
  - 1x4 の木口（厚み 19mm）に φ8 は置ける。φ10（`D(5, …)`）は 19 < 20 で `LayoutIssue`。
  - 接触面 38 × 38mm に φ10 は L/2 = 19 < 20 で中央に 1 本。
  - ビス: target は貫通（`depth=None`）、base は `length − 厚み`。
- プロパティ（hypothesis）: 有効なダボ・ビス接続をランダムに作り、
  - 各留め具の base 側と target 側の位置を世界座標（`solve_placement` の Pose）に移すと一致する
  - 位置は両部材の接触面内で、端から d 以上離れる
  - 本数は 1 か 2 でルールどおり。2 本のとき間隔は 2d 以上
  - `LayoutIssue` は接触面がない（辺でしか接しない）か S < 2d のときだけ
  - 面・辺の組み合わせ 24 × 24 すべてで例外が出ない
- build123d: ダボ穴の体積テスト（4 本 × πr² × 15）が新配置でも成り立つ。
- CLI: `validate` が留め具の問題を報告して終了コード 1、`export` が警告して終了コード 0 で続行。

## 完了条件

- `make ci-local` が通る。
- `examples/nd_files/*.nd` と docs / prompts / README の完全な設計例がすべて `validate` を通る
  （ダボが狭すぎて置けない設計例はドキュメント側を直す）。

## 挙動の変化

- ダボ・ビスの位置が新ルールの値になる（例: ±25.4mm → 接触面の 1/4 と 3/4）。
- これまで `NotImplementedError` で失敗していた面の組み合わせでも留め具が置ける。
- `Assembly.joints` / `joint_conns` と `find_joints_outside_pieces` は削除（互換レイヤーは置かない）。
