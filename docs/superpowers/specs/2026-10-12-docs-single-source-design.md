# ドキュメントの正本化（Docs Single Source）設計

- 日付: 2026-10-12
- ステータス: 実装済み（ブランチ docs/single-source）
- プロンプトの比較: 仕様の例 2 つ × 2 回を sonnet で生成。旧（system.md + presets.md + dsl-complete.md）4/4、新（system.md + DSL 仕様）4/4 が validate を通り全体寸法も仕様どおり。変数で寸法を書いたのは旧 3/4、新 4/4。
- 対象: M3-2（開発体験: ドキュメントの重複を減らす）

## 背景

機能を 1 つ足すたびに、DSL 仕様・API 仕様の英日、`prompts/system.md`、`prompts/reference/` の 3 ファイル、README の
6〜8 か所を直している。直し漏れも出た（ビスの長さの規則、`presets.md` の古い条件など）。

- DSL: `docs/dsl-specification.md`（634 行）・`_ja.md`、`prompts/system.md`（417 行）、`prompts/reference/dsl-complete.md`（144 行）
- Python API: `docs/api-specification.md`（914 行）・`_ja.md`、`prompts/reference/python-api.md`（511 行）
- README（590 行）: レポートの出力例、DSL の解説、Python API の例がドキュメントと重なる
- プリセットと材種の表はコードとも重なる

## 目的

仕様の正本を 1 か所にし、機能を足すときに直す場所を減らす。残る重複（例、表）は自動テストで食い違いを捕まえる。

## 合意した方針（決定事項と理由）

1. **ドキュメントは英語だけにする。** コード・コメント・README・プロンプトはもう英語なので、日本語版を消すと更新箇所が半分になる。
2. **正本は docs。** DSL は `docs/dsl-specification.md`、Python API は `docs/api-specification.md`。
3. **プロンプトは LLM 向けの部分だけを持つ。** 仕様は docs をそのまま LLM に渡す。プロンプトをスクリプトで組み立てる仕組みは
   作らない（重複はなくせるが仕組みが増える）。
4. **残る重複は自動テストで捕まえる。** ドキュメント中の例・表・リンク。

## スコープ外

- docs の書き直し（内容の変更は、統合と古い記述の修正に限る）
- プロンプトの作例・生成の規則の改善（M5 のプロンプトの回帰テストで扱う）
- `docs/superpowers/specs/`（決定の記録。日本語のまま残す）

## 設計

### 1. ファイル

- 削除: `docs/dsl-specification_ja.md`、`docs/api-specification_ja.md`、`prompts/reference/dsl-complete.md`、
  `prompts/reference/python-api.md`、`prompts/reference/presets.md`。
  - `dsl-complete.md` の JSON 記法・EBNF・エラー・CLI と、`presets.md` のプリセット表・ダボの深さの規則は、DSL 仕様に既にある。
  - `presets.md` にしかない「ビスの選び方」（部材の厚みの組み合わせごとの推奨長さ）は、DSL 仕様のビスの節へ移す。
  - `python-api.md` の内容は API 仕様に既にある。
- `prompts/system.md`: 残すのは出力の形式、定番の作例（Verified Patterns）、長さの計算、生成の規則とチェックリスト。
  「Core Concepts」「DSL Specification」の節は削り、「DSL の仕様は `docs/dsl-specification.md`（このプロンプトと一緒に渡す）」と案内する。
- `prompts/README.md`: 組み合わせ方を更新する。
  - .nd を出させる: `prompts/system.md` + `docs/dsl-specification.md`
  - Python を出させる: 上に `docs/api-specification.md` を足す
  - 例（`prompts/examples/`）は必要に応じて足す
- `README.md`: 概要・特徴・インストール・短い例（.nd 1 つと CLI）・開発コマンド・ドキュメントへのリンク・ライセンスに縮める（目安 150 行）。

### 2. 自動テスト（`tests/test_docs.py`）

対象: `docs/*.md`（`docs/superpowers/` を除く）、`README.md`、`prompts/**/*.md`。

1. **```nd の例:** すべて読め（`parse_dsl`）、配置の矛盾・部材の重なり・留め具の問題がない。つながっていない部材は可
   （部材の定義だけの例があるため）。断片（定義されていない部材を参照する接続、構文の雛形）は ```text で書く。
2. **API 仕様の例:** `docs/api-specification.md` の ```python ブロックのうち `>>>` を含むものを、ファイルの上から順に
   同じ名前空間で doctest として実行する（ELLIPSIS と NORMALIZE_WHITESPACE を有効にする）。
3. **表:** DSL 仕様の材種の表（型・幅・厚み）が `PieceType` と断面の表に、プリセットの表がダボ・ビスのプリセットの列挙に一致する。
4. **リンク:** Markdown の相対リンク（`[..](path)`、アンカーは除く）の先のファイルが存在する。

### 3. プロンプトの品質の確認（コミットしない）

前回（2026-10-11）と同じ方法で比べる: `prompts/examples/user-specs/` の 2 つの仕様 × 2 回、sonnet のサブエージェントに
旧（`system.md` + `presets.md` + `dsl-complete.md`）と新（`system.md` + `docs/dsl-specification.md`）で .nd を生成させ、
`validate` を通るか、全体寸法が仕様どおりかを数える。新が旧より悪ければ、足りない説明を `system.md` に戻す。

## 完了条件

- `make check` が通る（新しいテストを含む）。
- 消したファイルへの参照が残っていない（リンクのテストで確かめる）。
- プロンプトの比較で、新が旧より悪くない。
