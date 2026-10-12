# validate --json 設計

- 日付: 2026-10-12
- ステータス: 設計済み
- 対象: M3-3（開発体験: エージェントが設計ループで読む構造化した診断）

## 背景

設計スキルの効果の確認（2026-10-12）で、例にない 2x2 の花台は validate を 11 回・39 回呼び、18 分・31 分かかった。
エージェントは部材の位置を CLI で見られず、試しの .nd を作って座標を手探りしていた。

- 天板が 51mm はみ出した原因（どの部材がどちらにずれたか）を、最小構成のファイルと二分探索で突き止めていた。
- ダボ穴の衝突は「どの穴とどの穴が、どこで」が分からず、ダボを小さくしたり、ずらす量を試したりしていた。

validate の出力は人向けの文章だけで、位置も、問題に関わる部材や穴の場所も、機械で読める形では出ていない。

## 目的

エージェントが「どこがどうおかしいか」を推測せずに読めるようにする。成功の目安は、例にない依頼で validate の回数と時間が減ること。

## 合意した方針（決定事項と理由）

1. **`validate --json` を足す（別のコマンドにしない）。** 1 回の呼び出しで問題・部材の位置・外形が揃う。位置だけの
   コマンドを分けると、エージェントはほぼ毎回両方を呼ぶことになる。report に表を足す案は、report が既に大きく
   （棚で 27KB）機械向けでないので採らない。
2. **中身は「問題＋部材の位置と向き＋外形」。** 問題は種類と関わる部材・接続を項目に分け、穴の衝突には 2 つの穴の位置を
   付ける。すべての留め具と穴は出さない（出力が大きくなり、エージェントの文脈を圧迫する）。
3. **問題は構造化したデータを正本にし、文章はそこから作る。** テキストの出力・report の Warnings 節・JSON の `message` が
   食い違わない。
4. **人向けのテキスト出力は変えない。**

## スコープ外

- 画像での確認（M3-4）
- すべての留め具・下穴の一覧（report にある）
- JSON の版の管理（項目を足すことはあっても、消したり意味を変えたりするときに考える）

## 設計

### 1. JSON の形

`nichiyou-daiku validate --json FILE` は、結果にかかわらず次の JSON を 1 つ stdout に出す。終了コードはテキストと同じ
（問題もエラーもなければ 0、あれば 1）。長さの単位は mm。

```json
{
  "valid": false,
  "error": null,
  "overall_size": [400, 300, 700],
  "pieces": [
    {
      "id": "leg_fl", "type": "2x2", "length": 662, "group": 0,
      "min": [0, 0, 0], "max": [38, 38, 662],
      "faces": {"top": "+z", "right": "-x", "front": "-y"}
    }
  ],
  "problems": [
    {
      "kind": "hole_collision", "message": "dowel hole in 'leg_fl' runs into ...",
      "connection": ["leg_fl", "apron_left"], "other_connection": ["leg_fl", "apron_front"],
      "piece": "leg_fl", "fastener": "dowel",
      "holes": [
        {"entry": [19, 0, 640], "direction": "+y", "depth": 15, "diameter": 8},
        {"entry": [0, 19, 640], "direction": "+x", "depth": 15, "diameter": 8}
      ]
    }
  ]
}
```

- `valid`: `error` が null で `problems` が空のとき true。
- `error`: 読み込み・構文・意味・検証・組み立てで止まったとき `{"kind", "message", "line", "column"}`。
  `kind` はテキスト出力の見出しに対応する `file` / `syntax` / `semantic` / `validation` / `assembly` / `unexpected`。
  `line`・`column` は例外が持っていればその値、なければ null。このとき `overall_size` は null、`pieces`・`problems` は空。
- `overall_size`: 全部材を囲む箱の x・y・z の長さ（report の外形寸法と同じ値）。
- `pieces`: モデルの部材の順。
  - `type` は材種（`2x4` など）、`length` は解いた後の長さ。
  - `group` は配置のグループ（つながった部材の集まり）の番号。グループが 2 つ以上なら、グループ間の位置関係は決まっていない。
  - `min`・`max` はワールド座標の箱の角。原点は外形の箱の最小の角（全部材が 0 以上になる）。
  - `faces` は部材の top・right・front の面が向くワールドの方向（`+x` / `-x` / `+y` / `-y` / `+z` / `-z`）。
    down・left・back はその逆。DSL の面の名前のまま、どの面がどちらを向いているかが分かる。
- `problems`: テキスト出力と同じ順（配置の矛盾、未接続、留め具・穴の衝突（接続の順）、重なり）。全項目に `kind` と
  `message`（テキストと同じ文章）があり、`kind` ごとに次の項目を持つ。
  - `conflict`: `connection`（[base, target]）、`constraint`（`rotation` / `contact` / `flush` / `edge`）、`axis`、
    `mismatch_mm`（回転の矛盾では null）、`loop`（矛盾を作る部材の並び）
  - `unconnected`: `groups`（部材 ID の並びの並び）
  - `overlap`: `pieces`（[lhs, rhs]）、`volume_mm3`
  - `fastener`（留め具が置けない）: `connection`、`fastener`（`dowel` / `screw`）
  - `hole_collision`: `connection`（後の接続）、`other_connection`（先の接続）、`piece`（穴がぶつかる部材）、`fastener`、
    `holes`（後・先の順の 2 つの穴。`entry` は穴の入口の中心のワールド座標、`direction` は穴が進むワールドの方向、
    `depth`・`diameter`）
- 数値は `round_mm` で丸める。

### 2. コードの置き場所

- **core（`core/assembly/models.py`・`fasteners.py`）:** `LayoutIssue` に任意の項目を足す。
  - 穴の衝突のときだけ埋める: ぶつかる部材、相手の接続、2 つの穴（部材の座標での入口・進む軸と向き・深さ・径）。
  - `find_hole_collisions` が検出時に計算している `_Bore` から作る。core は build123d に依存しないまま。
- **shell（新規 `shell/diagnostics.py`）:** 出力のデータを作る。
  - pydantic の `Problem`（kind・message と kind ごとの任意の項目）、`PiecePosition`、`ValidationReport`（JSON の全体）。
  - `collect_problems(assembly) -> list[Problem]`: 矛盾・未接続・留め具・穴の衝突・重なりを 1 つの並びにする。
    部材の座標の穴はワールド座標に直し、外形の最小の角を原点にする。
  - `validation_report(assembly) -> ValidationReport`、`error_report(kind, exception) -> ValidationReport`。
  - `shell/resources.py` の `describe_assembly_issues` は `collect_problems` の `message`（重なりを除く。report は重なりを
    出していないため）から作る。文章は今と同じ。
- **cli（`cli/commands/validate.py`）:** `--json` フラグ。テキストの出力も `collect_problems` から作る。JSON のときは
  色や見出しを出さず、`--verbose` の要約も出さない。

### 3. スキルとドキュメント

- `skills/design/SKILL.md`
  - 手順 4: `nichiyou-daiku validate --json <name>.nd`。読み方を書く。部材の位置は `min`・`max` と `faces`、はみ出しは
    外形と各部材の箱の比較、穴の衝突は `holes`（どちらの接続をどの方向にどれだけずらすか）。
  - 手順 5: 外形は JSON の `overall_size` で依頼と比べる。report は最後に部材表と買い物リストを見るときだけ、
    `--no-cut-diagram --no-anchor-details --no-pilot-holes` を付けて使う（設計スキルのレビューで後回しにした #6）。
- `docs/dsl-specification.md` の CLI の節に `--json` と JSON の形を書く。例は `examples/nd_files/` の例ファイルの実際の
  出力そのものにする。

### 4. テスト

- `tests/shell/test_diagnostics.py`（新規）
  - 位置: 外形の最小の角が原点、`min`・`max` が `Pose.bounds` を平行移動したもの、`overall_size` が report と同じ。
  - `faces`: 回転していない部材は `top: +z, right: +x, front: +y`（局所座標の X=幅・Y=厚み・Z=長さ。front は +Y 側）、
    回転した部材はその回転どおり。
  - グループ: 未接続のモデルで `group` が分かれ、`unconnected` の問題が出る。
  - 問題の種類ごと: `conflict`・`unconnected`・`overlap`・`fastener`・`hole_collision` の各項目。穴の衝突は 2 つの穴の
    `entry` が部材の上にあり、`direction` が部材の内側を向く。
  - `message` が今のテキストと同じ（既存の report・validate のテストが通る）。
- `tests/cli/`: `--json` で JSON が stdout に出る、終了コード、構文エラーの `line`・`column`、標準入力、ファイルがない。
  テキストの出力は既存のテストで変わらないことを確かめる。
- `tests/test_docs.py`: DSL 仕様の JSON の例が、その例ファイルの実際の出力と一致する。

### 5. 効果の確認（コミットしない）

設計スキルのときと同じ方法で、3 依頼 × 2 回をやり直す（sonnet、非対話、リポジトリの外の空のディレクトリ、PATH から
`~/.local/bin` を外し、プラグインはクリーンなコピー）。

- 6/6 がスキルを使い、validate を通り、外形寸法が依頼どおり。
- 花台の validate の回数と時間の中央値が前回（11 回・39 回、18 分・31 分。中央値 25 回・24.5 分）より少ない。
- 花台の記録で、エージェントが `--json` の位置や穴を読んで直していること。

## 完了条件

- `make check` が通る（新しいテストを含む）。
- 効果の確認が上の 3 項目を満たす。満たさなければ SKILL.md の読み方を直して確かめ直し、2 回で届かなければ結果をユーザーに
  報告する。
