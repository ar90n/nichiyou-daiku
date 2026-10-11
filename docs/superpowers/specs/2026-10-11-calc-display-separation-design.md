# 計算と表示の分離（Calc/Display Separation）設計

- 日付: 2026-10-11
- ステータス: 実装済み（ブランチ refactor/calc-display-separation）
- 実装との差分: build123d は表題欄の文字などの線を実行のたびに違う順で SVG に書くため、変更前後の図面は「行の並び順を無視して」比べた（数値の差は丸めの 1e-6mm 以内）。
- 対象: リファクタリング・サブプロジェクト M2-2（計算と表示の分離）
- 前提: M2-1「部材配置のコア移行」、M2-3「留め具配置の作り直し」、片付け（2026-10-11）の上に作る

## 背景

- `shell/report_generator.py`（631 行）に、木取りの計算（`CutPlan`、`_optimize_cuts`、定尺、刃厚、定尺より長い部材）と
  Markdown の整形が同居している。同じ `_optimize_cuts` を「購入の推奨」と「木取り図」の 2 か所で呼んでいる。
- `cli/commands/drawing.py`（342 行）の CLI コマンドの中に、図面の計算（4 ビューの投影・縮尺・配置）がある。
  このファイルはカバレッジと pyright の対象外で、既存のテストはファイルの扱いしか見ていない。各ビューを 3 回投影している。

## 目的

挙動を変えずに、計算を表示と入出力から分ける。分けた計算をテストと型検査の対象にする。

## 合意した方針（決定事項と理由）

1. **範囲は木取りと図面の 2 つ。**
   - 診断の構造化は外す。コアはすでに構造化したデータ（`Conflict`、`LayoutIssue`、`Overlap`、`Placement.groups`）を
     返しており、文章にする部分も片付けで `shell/resources.describe_assembly_issues` にまとめた。
     `validate --json` を作るときは、これらをそのまま出せばよい。
   - `coordinates.py` の分割はやめる。削減で 388 行になり、座標の型としてまとまっている。
2. **木取りは `shell/cutting.py` に移す（案 A）。** 入力が shell の `PieceResource` で、定尺は買い物の話なので、
   コアに置く利点が薄い。`report_generator.py` の中で関数を分けるだけ（案 C）では、計算と表示が同じファイルに残る。
3. **図面は `shell/drawing.py` に移す（案 A）。** CLI に残すのは、DSL の読み込み、ファイルの書き出し、PDF への変換、エラー表示。
4. **投影は各ビュー 2 回にする（縮尺を決める 1 回と、仕上げの 1 回）。**
   - 今の 2 回目の投影は、縮尺を掛けたあとの範囲を知るためだけにある。縮尺を掛けた後の範囲は、縮尺前の範囲に縮尺を
     掛けたものと一致する（実測で差 1e-14mm）ので省ける。
   - 「1 回だけ投影して、線に縮尺を掛ける」方式は採らない。部材どうしが接している面の上の辺で、実線と点線の判定が
     変わるため（実測: `two-tier-shelf.nd` の正面図で実線の辺が 131 本 → 122 本）。

## スコープ外

- 定尺を CLI から設定する機能、金物リスト、図面への寸法記入、`validate --json`
- 木取りのアルゴリズム（first-fit decreasing）と図面のレイアウト（2x2、70%）の変更

## 設計

### 1. 木取り（`src/nichiyou_daiku/shell/cutting.py`、新規）

```python
DEFAULT_KERF_MM = 3.0
DEFAULT_STANDARD_LENGTHS: dict[PieceType, list[float]]  # 今の _get_default_standard_lengths() の値
FALLBACK_STANDARD_LENGTHS = [2440.0]                     # standard_lengths にない材の種類に使う（今と同じ）

@dataclass
class CutPlan:                 # 1 枚の定尺材の切り方（今と同じ）
    board_length: float
    cuts: list[tuple[str, float]]
    waste: float

@dataclass
class LumberPlan:              # 1 種類の材の木取り
    available_lengths: list[float]
    boards: list[CutPlan]
    oversize: list[PieceResource]    # どの定尺材より長い部材

    board_counts: dict[float, int]   # property: 定尺の長さごとの枚数
    total_waste: float               # property
    waste_percentage: float          # property: 購入した長さに対する端材の割合（購入 0 なら 0）

def plan_cuts(
    summary: ResourceSummary,
    standard_lengths: Mapping[PieceType, Sequence[float]] | None = None,
    kerf: float = DEFAULT_KERF_MM,
) -> dict[PieceType, LumberPlan]:
    """材の種類ごとの木取り。キーは PieceType.value の順（レポートの節の順）。"""
```

- `_optimize_cuts` と `_oversize_pieces` は中身を変えずに `cutting.py` へ移す（非公開のまま）。
- `report_generator.generate_markdown_report` の引数は変えない。中で `plan_cuts` を 1 回呼び、
  `_generate_purchase_recommendations(plans)` と `_generate_cut_list(plans)` はその結果を整形するだけにする。
- `CutPlan` / `plan_cuts` は `shell/__init__` から公開しない（使う側がまだない）。

### 2. 図面（`src/nichiyou_daiku/shell/drawing.py`、新規）

```python
PAGE_SIZES = ("A4", "A3", "A2", "A1")

def technical_drawing(
    part: Compound,
    *,
    title: str,
    drawing_number: str,
    designed_by: str,
    page_size: str = "A3",
    design_date: date | None = None,   # None なら今日
) -> ExportSVG:
    """上面・正面・右側面・等角の 4 ビューと枠を、Visible / Hidden の 2 レイヤーに描いた図面。"""
```

- 中身は今のコマンドと同じ計算: 枠（`TechnicalDrawing`）、2x2 の配置、すべてのビューに共通の縮尺
  （最も大きいビューがマス目の 70% に収まる）、各ビューの中心をマス目の中心に置く。
- 投影は決定 4 のとおり各ビュー 2 回。
- `build123d` はモジュールの先頭で import する（`shell/__init__` からは import しない。CLI は build123d の有無を
  確かめてから import する）。
- CLI（`cli/commands/drawing.py`）: オプションと出力（SVG / PDF、一時ファイル、上書き防止）は今と同じ。
  図面を作る処理の失敗は、今の 3 つのメッセージ（枠・投影・SVG）を 1 つ（`Error creating drawing: ...`）にまとめる。
- `pyproject.toml`: カバレッジの `omit` と pyright の `exclude` から `cli/commands/drawing.py` を外す。

## テストと確認

### 挙動が変わらないことの確認（一度だけ。コミットしない）

- 変更前に保存し、変更後と比べる:
  - レポート: `examples/nd_files/*.nd`、`prompts/examples/nd-output/*.nd`、`examples/long_shelf.py` のモデルについて、
    定尺は既定値と独自の値、`include_cut_diagram` は True / False。日付の行を除いて完全一致すること。
  - 図面: `prompts/examples/nd-output/*.nd` の SVG（A3 と A4）。完全一致、または数値の差が 1e-6mm 以下であること。

### コミットするテスト

- `tests/shell/test_cutting.py`: 今の `_optimize_cuts` / `_oversize_pieces` / 既定の定尺のテストを移す。
  `plan_cuts` のテスト: 既定の定尺、`standard_lengths` にない種類は 2440mm、定尺より長い部材が `oversize` に入り
  `boards` に入らない、`board_counts` / `total_waste` / `waste_percentage`。
- `tests/shell/test_report_generator.py`: 残る整形のテストを新しい関数の形に合わせる。
- `tests/shell/test_drawing.py`（build123d がなければ skip）: 4 ビューがすべて枠の描画範囲に収まり互いに重ならない、
  最も大きいビューがマス目の 70% に収まる、Hidden レイヤーに線がある、`page_size` を変えると枠の大きさが変わる。
- 既存の `tests/cli/commands/test_drawing.py` はそのまま通ること。

## 完了条件

- 上の確認で、レポートと図面が変わっていない。
- `make ci-local` が通る（カバレッジ 90% 以上。`drawing.py` を計測対象に戻した状態で）。
- `report_generator.py` から木取りの計算がなくなり、`cli/commands/drawing.py` から投影の計算がなくなる。
