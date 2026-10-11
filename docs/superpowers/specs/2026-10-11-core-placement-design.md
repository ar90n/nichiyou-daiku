# 部材配置のコア移行（Core Placement）設計

- 日付: 2026-10-11
- ステータス: 実装済み（ブランチ refactor/core-placement）
- 実装との差分（以下の本文は合意時の記録）:
  - `Pose` の 4x4 行列メソッドは作っていない（使う場所がないため）。
  - `Placement.free_axes` は常に空だったため後に削除した（部分拘束を入れるときに足す）。
  - `validate` の「部材外のダボ」検出（`find_joints_outside_pieces`）は M2-3 の留め具配置で不要になった。
- 対象: リファクタリング・サブプロジェクト 1/4（配置をコアへ）

## 背景

部材のワールド配置は、現在 `shell/build123d_export.py` の中で build123d の `RigidJoint.connect_to` を
幅優先で順につなぐことでしか計算されていない。その結果、次の問題がある。

- 配置が必要な処理（重なり・矛盾の検出、全体寸法、図面）がすべて build123d / OCCT のソリッド生成を要する。
  build123d は任意依存で、ARM64 では動かず、処理も秒単位で遅い。
- `connect_to` を順につなぐ仕組みのため、矛盾する接続があると後から処理した接続が勝つ（順序依存）。
- 配置結果が OCCT オブジェクトの内部にあり、`intersect` が joint を付け替えて結果を壊す副作用があった。
- コアに配置がないため、配置のバグをコアのテストで捕まえられない。

## 目的

全接続を同時に満たす配置をコアで厳密に求める。build123d は求めた位置にソリッドを置く描画係にする。

## 合意した方針（決定事項と理由）

1. **接続を自由度ごとの拘束に分解して解く。** 1 本の接続は回転 3 自由度と並進 3 自由度を拘束する。
   並進は「密着（contact）」「面一（flush）」「辺上の一致（edge）」の 3 本のスカラー拘束に分ける。
   将来、一部の自由度だけを拘束する接続や未知数（長さ・オフセット）を足せる構造にするため。
2. **回転は 90° 刻みの離散値として厳密に扱う。** 連続変数にしない。行列の成分は −1/0/1 のみ。
3. **並進は軸ごとに厳密に解く。** 最小二乗で誤差を全体に広げない。満たせる拘束は誤差 0 で満たす。
4. **矛盾時は先に宣言した接続を優先する。** 矛盾した拘束だけを、ずれ量とループとともに報告する。
   矛盾のないモデルでは、結果は接続の順序に依存しない。
5. **export / report / view / drawing は、矛盾やつながっていない部材群があっても警告して続行する。**
   `validate` はエラー（終了コード 1）として報告する。
6. 最小二乗は、将来未知数を導入したときに「解けるか（残差 0 か）」の判定にのみ使う。今回は使わない。

## スコープ外

- 新しい種類の接続（部分拘束）、長さ・オフセットの未知数化（DSL での表記を含む）
- JSON 出力（`validate --json` 等）
- 接合 ID の型付け・`Assembly.joints` / `joint_conns` の再設計（サブプロジェクト 3 で扱う）
- ダボ配置アルゴリズムの作り直し（サブプロジェクト 3）

## 設計

### 1. データモデル（`src/nichiyou_daiku/core/placement.py`）

純粋計算。依存は numpy とコア内モジュールのみ。データクラスは既存規約どおり frozen な pydantic モデル。

```python
Axis = Literal["x", "y", "z"]
ConstraintKind = Literal["rotation", "contact", "flush", "edge"]

class Pose(BaseModel, frozen=True):
    rotation: tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]
    translation: tuple[float, float, float]
    # 点の変換、4x4 行列、部材の世界座標の外形（AABB）を返すメソッドを持つ

class Conflict(BaseModel, frozen=True):
    base_id: str
    target_id: str
    kind: ConstraintKind
    axis: Axis | None          # rotation のときは None
    mismatch_mm: float | None  # rotation のときは None
    loop: tuple[str, ...]      # 矛盾を構成する部材の経路（base ... target）

class Placement(BaseModel, frozen=True):
    poses: dict[str, Pose]
    groups: tuple[tuple[str, ...], ...]   # 互いにつながっている部材群（各群は宣言順）
    conflicts: tuple[Conflict, ...]
    free_axes: dict[str, frozenset[Axis]] # 群の基準に対して位置が決まらない軸。現行の接続では常に空

class Overlap(BaseModel, frozen=True):
    lhs: str
    rhs: str
    volume: float  # mm^3

def solve_placement(model: Model) -> Placement: ...
def find_overlaps(model: Model, placement: Placement) -> tuple[Overlap, ...]: ...
def overall_bounds(model: Model, placement: Placement) -> tuple[Point3D, Point3D]: ...
```

`Assembly.of(model)` は `placement=solve_placement(model)` を計算して `Assembly.placement` に持たせる。
利用側は従来どおり `Assembly` を受け取る。

### 2. ソルバー

部材の座標系は既存どおり X=幅、Y=厚み、Z=長さ。接続の処理順は `model.connections` の挿入順（DSL の宣言順）。

**前準備（接続ごと）**: base / target それぞれの部材座標系で
アンカー点 `p`（`as_point_3d`）、接触面の外向き法線 `n`、辺共有面の外向き法線 `e` を求める。
target 座標系から base 座標系への相対回転 `R_rel` を次で定める（第 3 軸は外積で決まる）。

```
R_rel · n_B = −n_A        （接触面が向かい合う）
R_rel · e_B =  e_A        （辺共有面が同じ向き＝面一）
R_rel · (n_B × e_B) = −(n_A × e_A)
```

`R_rel` は必ず符号付き置換行列（行列式 +1）になる。

**手順 1（回転）**: 接続を順に処理し、部材群と群の基準に対する回転を管理する（群の併合時は小さい群側の
全部材の回転を更新）。同一群内の接続は `R_target == R_base · R_rel` を整数行列として完全一致で判定し、
不一致なら `Conflict(kind="rotation")` を記録して、その接続の並進拘束は使わない。

**手順 2（並進・軸ごと）**: 採用した接続について `t_Q + R_Q·p_B = t_P + R_P·p_A` を X/Y/Z の 3 式に分ける。
各ワールド軸がどの拘束か（`R_P·n_A` の軸 → contact、`R_P·e_A` の軸 → flush、残り → edge）を記録する。
軸ごとに重み付き Union-Find（親へのオフセットを持つ）で差分制約 `t_Q[k] − t_P[k] = c` を処理する。
別群なら併合し、同一群なら `|差 − c| ≤ 1e-6 mm` を確認する。超えたら
`Conflict(kind, axis, mismatch_mm=c − 差, loop)` を記録する（差は採用済み拘束から決まる
`t_Q[k] − t_P[k]`）。`loop` は採用済み拘束をたどった base から target までの経路で、両端を含む
（BFS、隣接は宣言順にたどるので決定的）。

**手順 3（正規化）**: 各群の基準を、群内で最初に宣言された部材とし、その部材が回転なし・原点になるよう
群全体を変換し直す。並進は `round(v, 6) + 0.0` で丸める。これにより矛盾のないモデルでは結果が接続順に依存しない。

**手順 4（群の配置）**: 群は基準部材の宣言順に並べる。2 つ目以降の群は、直前までの群の外形の
最大 X から +100 mm の位置にその群の最小 X が来るよう +X 方向に平行移動する。

**free_axes**: 軸 k について、部材が群の基準と同じ Union-Find 集合に属さない場合にその軸を含める。
現行の接続は 3 軸すべてを拘束するため常に空。

計算量は部材数 N に対し最悪 O(N²)。家具規模（〜100 部材）では問題にならない。

### 3. 重なりと全体寸法

部材は常にワールド軸に沿った直方体なので、`Pose` から各部材の AABB を求め、区間の交差で重なり体積を
厳密に計算する（穴・面取りは無視）。体積 > 1e-6 mm³ の組を `Overlap` として返す。
`overall_bounds` は全部材の AABB の和の最小・最大点を返す。

### 4. shell（`build123d_export.py`）

- `assembly_to_build123d`: 部材ごとのソリッド生成（面取り・穴あけ）は部材座標系のまま行い、
  `Pose` を `Location(Plane(origin=translation, x_dir=R[:,0], z_dir=R[:,2]))` で適用して配置する。
- 削除: `_as_euler_angles`, `_create_joint_from`, `_connect`, RigidJoint によるたどり処理,
  `find_joint_mismatches`, OCCT による `check_overlap` と `OverlapResult`, `_common_volume`,
  `_bounding_boxes_overlap`。`shell/__init__.py` の公開名も合わせて整理する（互換レイヤーは置かない）。

### 5. CLI

- `validate`: build123d 不要。次を報告し、1 件でもあれば終了コード 1。`--no-geometry` は削除する。
  - 回転の矛盾: `Connection a -> b: orientation contradicts the other connections (loop: ...)`
  - 軸の矛盾: `Connection apron_left -> leg_3: flush (y) is off by 24.0mm (loop: leg_1 -> apron_front -> leg_2 -> apron_left -> leg_3)`
  - つながっていない部材群（既存メッセージ）
  - 重なり: `Pieces 'a' and 'b' overlap (1234.0mm³)`
  - 部材外のダボ（既存 `find_joints_outside_pieces`）
- `export` / `view` / `drawing` / `report`: `cli/utils.warn_placement_issues(assembly, echo)` で
  矛盾とつながっていない部材群を標準エラーに警告し、処理を続行する（終了コード 0）。
- `report`: 概要に外形寸法を追加する。
  例: `- **Overall Size (X × Y × Z)**: 800 × 500 × 720 mm (Z is the length direction of 'leg_1')`

### 6. ドキュメント

`check_overlap`・`find_joint_mismatches`・`--no-geometry` への言及を削除し、`validate` が build123d なしで
動くこと、矛盾時の警告挙動、report の外形寸法を記載する（README, docs/, prompts/, CLAUDE.md）。

## テストと移行

### 移行手順

1. `core/placement.py` と `Assembly.placement` を追加する（shell は未変更）。
2. 照合テスト: 新しい `Pose` から求めた各部材の AABB が、現行の RigidJoint 配置の build123d 外形
   （`fillet_radius=0`、各部材の `bounding_box()`）と 1e-6 mm 以内で一致することを、次で確認する。
   - 有効なアンカーの組み合わせすべて（base 24 × target 24、vanilla、2x4 同士）
   - `examples/nd_files/*.nd`
   - docs / prompts / README 内の完全な設計例
3. 全件一致を確認したら shell を `Pose` 配置に切り替え、RigidJoint 方式を削除する。
   照合テストは期待値を固定した回帰テストに置き換えて残す。
4. CLI と ドキュメントを更新する。

### テスト

- プロパティベース（hypothesis）
  - 有効な接続をランダムに組んだ木では矛盾が出ない。
  - 配置後、全接続でアンカー点が一致し、接触面法線が逆向き、辺共有面法線が同じ向き。
  - 接続の宣言順を入れ替えても `Pose` が完全に一致する。
  - 回転行列は常に符号付き置換行列で行列式 +1。
  - 整合した冗長接続（ループ）を足しても矛盾が出ない。そのオフセットを d mm ずらすと、
    予想どおりの軸・種類で `mismatch_mm = ±d` の矛盾がちょうど 1 件出る。
- 単体テスト: 回転の矛盾、軸の矛盾（contact/flush/edge の判定とループ）、群の並べ方、
  `find_overlaps`（接触のみは 0、重なりは厳密な体積）、`overall_bounds`。
- CLI テスト: `HAS_BUILD123D=False` でも `validate` が重なり・矛盾を検出する。
  矛盾のあるモデルで `export` / `report` が警告して終了コード 0 で続行する。report に外形寸法が出る。

## 完了条件

- `make ci-local` が通る。
- `examples/nd_files/*.nd` と docs の設計例がすべて `validate` を通る。
- 照合テストにより、既存モデルの部材配置が移行前と一致することを確認済み。

## 今後（別サブプロジェクト）

- 2: 計算と表示の分離、大きいファイルの分割（挙動不変）
- 3: 接合の作り直し（ダボ・ビスの汎用配置、接触面の重なり領域の利用、1 ペア複数接続、接合 ID の型付け）
- 4: 材種・DSL の拡張（部分拘束の接続、長さ・オフセットの未知数化を含む）
