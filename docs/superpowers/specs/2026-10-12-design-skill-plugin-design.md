# 設計スキルとプラグイン（Design Skill Plugin）設計

- 日付: 2026-10-12
- ステータス: 設計済み
- 対象: M3-2 の続き（ブランチ docs/single-source で、main に入れる前に行う）。M5（エージェントの設計ループ）の土台

## 背景

`prompts/` は、API にシステムプロンプトとして貼る使い方を前提にしている。いまの使い方は、Claude Code のエージェントが
CLI を回しながら設計するものだ。プロンプトには「validate で確かめて直す」手順を書けず、エージェントは CLI の場所も知らない。

また nichiyou-daiku は PyPI にない。README の `pip install nichiyou-daiku` は動かない。

## 目的

Claude Code で「2x4 で幅 600 のサイドテーブルを作りたい」と頼むと、エージェントが .nd を書き、CLI で確かめて直し、
外形寸法と材料をまとめて返す。利用者がするのは `/plugin` の 2 コマンドだけ。

## 合意した方針（決定事項と理由）

1. **スキルを先に作る。** `validate --json` と画像での確認は M3-3・M3-4 で足し、M5 でスキルを磨く。
2. **プラグインとして配る。** リポジトリ自身をマーケットプレイスにする。別リポジトリにしないのは、スキルが参照する docs と、
   CLI のソースを同じコミットで持てるから。
3. **スキルの範囲は設計ループ。** 要件 → .nd → validate → 直す → report。Python コードは生成しない
   （CLI で確かめられるのは .nd だけ）。
4. **CLI は両方に対応する。** 入っている `nichiyou-daiku` があればそれを使い、なければ同梱のソースを uv で動かす。
   PyPI にないので、何も入れていない人も動かせるようにする。
5. **`prompts/` は消す。** 中身はスキルへ移す。

## スコープ外

- `validate --json`、画像での確認（M3-3、M3-4）
- PyPI への公開、版の付け方
- claude.ai・Cowork での配布（`bin/` を持つプラグインは入れられない）
- スキルの評価の自動化（M5 の回帰テストで扱う）

## 設計

### 1. プラグインとマーケットプレイス

リポジトリのルートがそのままプラグインのルートになる（インストールされたコピーに docs と src も入る）。

`.claude-plugin/plugin.json`:

```json
{
  "name": "nichiyou-daiku",
  "description": "Design DIY furniture from standard 1x/2x lumber with the nichiyou-daiku DSL and CLI",
  "author": { "name": "Masahiro Wada" },
  "homepage": "https://github.com/ar90n/nichiyou-daiku",
  "repository": "https://github.com/ar90n/nichiyou-daiku",
  "license": "Apache-2.0",
  "keywords": ["woodworking", "diy", "furniture", "cad"]
}
```

`version` は書かない。書くとその版に固定され、利用者に新しいコミットが届かなくなる。

`.claude-plugin/marketplace.json`:

```json
{
  "name": "nichiyou-daiku",
  "owner": { "name": "Masahiro Wada" },
  "description": "The nichiyou-daiku plugin for Claude Code",
  "plugins": [
    {
      "name": "nichiyou-daiku",
      "source": "./",
      "description": "Design DIY furniture from standard 1x/2x lumber with the nichiyou-daiku DSL and CLI"
    }
  ]
}
```

- 入れ方: `/plugin marketplace add ar90n/nichiyou-daiku` → `/plugin install nichiyou-daiku@nichiyou-daiku`
- 開発中: `claude --plugin-dir .`
- ドットファイルをコミットしない規則には、`.github/` と同じく `.claude-plugin/` を例外として加える（ローカルの CLAUDE.md）。

### 2. スキル（`skills/design/`、呼び名 `nichiyou-daiku:design`）

```
skills/design/
├── SKILL.md         # 設計ループの手順
├── patterns.md      # 定番の作例・長さの計算・命名・チェックリスト（旧 prompts/system.md）
├── requirements.md  # 要件として確かめる項目（旧 prompts/user-template.md）
└── examples/        # 要件と、それを満たす .nd の組
    ├── side-table.md, side-table.nd
    ├── two-tier-shelf.md, two-tier-shelf.nd
    └── corner-joint.nd
```

`SKILL.md` の frontmatter:

```yaml
---
name: design
description: Design DIY furniture from standard 1x/2x SPF lumber (1x4, 2x4, 2x2, ...) as a nichiyou-daiku .nd file, then check and fix it with the nichiyou-daiku CLI. Use when the user wants to design, size or change a table, shelf, bench, rack or other furniture built from 2x4/1x4 lumber, or works on a .nd file.
---
```

本文（英語）の手順:

1. **要件をそろえる。** `requirements.md` の項目（外形 W×D×H、材種、脚・幕板・天板・棚、接合）のうち、
   依頼にないものだけを聞く。利用者がこだわらない項目は既定値を置き、置いた値を伝える。
2. **読む。** `${CLAUDE_PLUGIN_ROOT}/docs/dsl-specification.md` と `patterns.md`。似た例があれば `examples/` も。
3. **書く。** 利用者のプロジェクトに `<name>.nd` を作る。外形は変数にし、長さとオフセットは式で書く。
4. **確かめて直す。** `nichiyou-daiku validate <name>.nd` が通るまで直す。同じエラーが 3 回直らなければ、
   状況を説明して利用者に聞く。
5. **要件と照らす。** `nichiyou-daiku report <name>.nd` の外形寸法を依頼と比べ、部材表と買い物リストを確かめる。
6. **頼まれたら出力する。** `drawing`（PDF の図面）、`export`（STL・STEP）。初回は build123d を入れるので数分かかると伝える。
7. **報告する。** ファイルの場所、外形寸法、買う材料、残った警告。

docs はスキルにコピーせず、`${CLAUDE_PLUGIN_ROOT}` で参照する（Claude Code がスキル本文の中で絶対パスに置き換える）。
スキル内のファイルは Markdown の相対リンクで示す。

`prompts/` からの移し方:

- `system.md` → `patterns.md`: 定番の作例、長さの計算、命名、接続の順、コメント、チェックリストを残す。
  出力形式（Python を含む）、DSL 仕様への案内、図面での確認は SKILL.md の手順に吸収して消す。
- `user-template.md` → `requirements.md`: 出力形式の行を消す。
- `examples/user-specs/*.md`、`examples/nd-output/*.nd` → `skills/design/examples/`
- `examples/python-output/simple-table.py` → `examples/side_table_api.py`（API の例として残す）
- `README.md` は消す（API にプロンプトを貼る手順は、スキルで置き換わる）。

### 3. CLI（`bin/nichiyou-daiku`、POSIX sh、実行権限付き）

プラグインが有効な間、`bin/` は Bash ツールの PATH に入る。`CLAUDE_PLUGIN_ROOT` は Bash の環境には入らないので、
スクリプトは自分の場所（`$0`）からプラグインのルートを求める。

1. **入っている CLI を使う。** PATH から `nichiyou-daiku` を探し、自分の `bin/` を除いて最初に見つかったものを exec する。
   別のプラグインのコピー同士で呼び合わないよう、環境変数 `NICHIYOU_DAIKU_WRAPPED=1` を付けて exec し、
   これが付いて呼ばれたら探さずに 2 へ進む。
2. **同梱のソースを uv で動かす。** `uv` があれば、プラグインのルートのソースで CLI を動かす。引数に `export`・`drawing`・
   `view` があれば viz の extra（build123d）を加える。方式は実装の最初に小さく試して決める。
   - 候補 A: `uvx --from <root>`（extra 付きは `nichiyou-daiku[viz] @ <root>` の形）
   - 候補 B: `uv run --project <root> --frozen --no-dev`、仮想環境は `UV_PROJECT_ENVIRONMENT` で
     `${XDG_CACHE_HOME:-~/.cache}/nichiyou-daiku/` の下に置く（`uv.lock` と同じ版で動く）
   - 決め手: viz が動く（build123d は `tool.uv.sources` の git から入る）、プラグインのルートに何も書かない、
     2 回目からすぐ起動する。どちらも満たすなら B（CI と同じ版で動く）。
3. **どちらもなければ** 標準エラーに入れ方（uv、または `uv tool install` での CLI の入れ方）を出し、終了コード 127 で終わる。

### 4. 片付け

- `prompts/` を消す（上の移し方で）。
- `README.md`:
  - 「Use with Claude Code」の節を足す（`/plugin` の 2 コマンドと、頼み方の例 1 つ）。
  - インストールを GitHub からに直す（`uv tool install "git+https://github.com/ar90n/nichiyou-daiku"`、viz 付きの形も）。
    コマンドは実際に試して確かめる。
  - ドキュメントの一覧の「LLM prompts」をスキルへのリンクに替える。
- ローカルの CLAUDE.md: ドットファイルの例外、構成（`.claude-plugin/`、`skills/`、`bin/`）、ドキュメントの場所。

### 5. テスト

`tests/test_docs.py`:

- `MARKDOWN` を `docs/*.md` + `README.md` + `skills/**/*.md` に、`ND_FILES` を `examples/nd_files/*.nd` +
  `skills/design/examples/*.nd` に替える。
- Python の例のテストは `examples/side_table_api.py` を読む。
- 本文に書かれたパスの検査に `skills/` と `bin/` を加え、`${CLAUDE_PLUGIN_ROOT}/<path>` はリポジトリのルートから解決する。

`tests/test_plugin.py`（新規）:

- `plugin.json` の `name` が `nichiyou-daiku`、`version` がない。`marketplace.json` の `name`・`owner.name` があり、
  エントリが 1 つで、`name` が `plugin.json` と同じ、`source` が `./`。
- `skills/*/SKILL.md` の frontmatter: `name` がディレクトリ名と同じ、`description` が空でなく 1024 文字以内。
- `bin/nichiyou-daiku`: 実行権限がある、`sh -n` が通る。偽の `nichiyou-daiku`・`uv` を置いた PATH で動きを確かめる。
  - 別の `nichiyou-daiku` が PATH にあれば、引数をそのまま渡してそれを動かす（自分より前でも後でも）。
  - なければ `uv` を呼ぶ。`export` などがあれば viz の extra を付け、`validate` では付けない。
  - `NICHIYOU_DAIKU_WRAPPED=1` で呼ばれたら、PATH の CLI を探さない（自分のコピーが 2 つあっても呼び合わない）。
  - どちらもなければ終了コード 127 で、入れ方を出す。

手で確かめること（コミットしない）:

- `claude plugin validate` が、クリーンなチェックアウトでエラーなしに通る。
- PATH に nichiyou-daiku がない環境で、`bin/nichiyou-daiku validate` と `drawing` が uv 経由で動き、
  プラグインのルートに何も書かない。
- `claude --plugin-dir` で読み込むと、スキルが `nichiyou-daiku:design` として見える。

### 6. 効果の確認（コミットしない）

空の一時ディレクトリで、プラグインを読み込んだ Claude Code（sonnet）を非対話で動かす:
`claude -p --model sonnet --plugin-dir <repo> --output-format stream-json ...`（Read・Write・Edit と `nichiyou-daiku` の
Bash を許可する）。依頼は日本語の自然文で 3 つ × 2 回:

- サイドテーブル（`skills/design/examples/side-table.md` の要件）
- 2 段の棚（`skills/design/examples/two-tier-shelf.md` の要件）
- 新しい材種を使うもの（2x2 の花台など、例にない形）

数えること: スキルが呼ばれたか（ストリームの Skill の呼び出し）、.nd が `validate` を通るか、外形寸法が依頼どおりか、
validate で直すループが回ったか。

## 完了条件

- `make check` が通る（新しいテストを含む）。
- `prompts/` がなく、参照も残っていない（パスとリンクのテストで確かめる）。
- 手で確かめる 3 項目が通る。README のインストールのコマンドが動く。
- 効果の確認で、6 回すべてスキルが呼ばれ、validate を通り、外形寸法が依頼どおり。届かなければ SKILL.md・patterns.md を
  直して確かめ直す。
