# 評価で LLM を選べるようにする（M5-2 の状況確認）設計

- 日付: 2026-10-18
- ステータス: 実装済み（試運転、Opus の最終レビューを反映）
- 対象: M5-2（設計の質を上げる）の最初の一歩。直す前に、今のスキルの状況を確かめる

## 背景

M5-1 で設計スキルの評価（`make eval`・`make eval-full`、`evals/design/`）を作った。ベースラインでは ★ の 5 件が
すべて合格し、`make eval` は天井に張り付いた（2026-10-18-design-eval-design.md §8）。設計させるモデルは
Claude Code（`claude -p`）の sonnet だけで、ほかの LLM では回せない。

M5-2 の目標（ユーザー）: ①評価の合格率を上げる、③1 回の時間と使用量を減らす。あわせて、同じスキルが DeepSeek や
GLM でも動くことを確かめたい。直し方は、状況を見てから決める。

## 目的

- `make eval` / `make eval-full`（と `python -m evals.design.run`）で、設計させる LLM を選べる。Claude Code の
  モデル（sonnet・opus・haiku）と、opencode で動かすモデル（DeepSeek・GLM ほか）。
- どの LLM も同じスキル（`skills/design/`）を読む。スキルは道具に依存しない書き方にする。
- 状況確認として、sonnet・DeepSeek・GLM でそれぞれ `make eval-full` を並列に回し、結果を並べて見る。

## 決定と理由

1. **LLM を選べるようにし、毎回すべては回さない**（ユーザー）。状況確認では、3 つの評価を別々に並列に回す。
   1 回の評価は 1 つの LLM だけを測り、結果も別々のディレクトリに出す。
2. **DeepSeek と GLM は opencode で動かす**（ユーザー）。今使えるのは opencode の無料版
   （`opencode/deepseek-v4.1-flash-free`、`opencode/glm-5.3-flash-free`）で、`deepseek`・`glm` の短い名前で
   選べるようにする。有料版（`opencode-go/...`）は OpenCode Go のキーが期限切れで使えない。キーを更新すれば正式な
   名前（`opencode/...`・`opencode-go/...`）で選べる。無料版の名前は opencode の都合で変わるので、短い名前の表は
   評価の仕組みの 1 か所に置く。
   **更新（2026-11-03、ユーザー）**: OpenCode はサブスク（OpenCode Go、`opencode-go/…`）だけを使う。短い名前は
   `deepseek` → `opencode-go/deepseek-v4.1-flash`、`glm` → `opencode-go/glm-5.3-flash`。`opencode/…`（OpenCode Zen、
   無料版も含む）は従量課金の別枠なので、名前を見て止める。
3. **どの LLM も同じスキルを読む**（ユーザー）。スキルを道具ごとに分けたり書き換えたりしない。Claude Code には
   これまでどおり `--plugin-dir` でプラグインの写しを渡す。opencode には、回ごとの opencode の設定ファイルの
   `skills.paths` でプラグインの写しの `skills/` を指して渡す（確かめた）。スキルは写しの中にあるので、スキルから
   見た `../../docs/` に DSL 仕様がある。最初は作業ディレクトリに `.opencode` → 写しのリンクを置く案だったが、
   それだとエージェントの作業ディレクトリにプラグインの中身が見えるので、設定で渡す形にした（計画のとき）。
4. **スキルは `${CLAUDE_PLUGIN_ROOT}` を使わない**。Claude Code だけが展開する変数で、opencode では展開されない。
   試しに DeepSeek に読ませると、仕様の場所が分からず `find /` でディスク全体を探した。DSL 仕様は SKILL.md からの
   相対リンク（`../../docs/dsl-specification.md`）で示す。Claude Code はスキルのベースディレクトリを、opencode は
   スキルの場所を示すので、どちらでもたどれる。Web サービスへの扉（M5-1 の決定 1）にもなる。
   2026-10-12-design-skill-plugin-design.md の「docs は `${CLAUDE_PLUGIN_ROOT}` で参照する」はこれで置き換わる。
5. **opencode も切り離して動かす**。設定（`XDG_CONFIG_HOME`）とセッションの記録（`XDG_DATA_HOME`）を一時
   ディレクトリにし、`OPENCODE_DISABLE_CLAUDE_CODE=1` で `~/.claude` のスキルや CLAUDE.md を読ませない。
   確かめた（2026-10-18）: スキルは opencode 組み込みの 1 つとこのスキルだけになり、無料版は認証なしで動いた。
   そうしないと、ユーザーの `~/.claude/skills`（memory など）まで読み、ユーザーの opencode の履歴に評価が混ざる。
   最終レビューで足した（実装のとき）: 回ごとの `TMPDIR`（opencode はエージェントに `<tmp>/opencode` を作業場所として
   勧め、そこはユーザーのセッションやほかの回と共有だった。GLM の試運転がそこに書いた）、評価ごとの `XDG_STATE_HOME`
   （ロックがユーザーの `~/.local/state/opencode` に残っていた）、`OPENCODE_DISABLE_EXTERNAL_SKILLS=1`（`~/.agents/skills`
   も読まない）と、引き継いだ `OPENCODE_*` の変数を外す。事前の確認の `opencode models` も一時ディレクトリで動かす
   （リポジトリで動かすと `.git/opencode` を書いた）。
   PATH と CLI は Claude Code の回と同じ（プラグインの写しの `bin/` が先頭、開発用の `.venv` は外す）。
6. **断る道具は Claude Code の回とそろえる**。opencode は `--auto`（明示的に断ったもの以外は許す）で動かし、
   一時的な設定ファイルの `permission` で、`rm`・`git`・`curl`・`wget`・`ssh`・`sudo`・`uv tool`・`pip` と
   Web の取得・検索を断る。道具の違いで結果が変わらないようにする。サブエージェント（`task`）も断る: Claude Code の回は
   使えず、opencode の記録にはサブエージェントの動きが出ないので、トークンや validate の数が黙って少なくなる
   （実装のとき、最終レビューで指摘）。
7. **採点役はどの LLM の回も opus（`claude -p`）**。採点がそろわないと、LLM どうしを比べられない。
8. **速く安くの物差しにトークンを足す**。無料版は費用が 0 なので、USD では比べられない。入力と出力のトークン数を、
   どの LLM の回もレポートに出す（Claude Code の回も）。
9. **opencode の一時的な失敗は失敗した試行**。無料版はときどき 503（`Endpoint is unavailable`）を返す（試しで
   一度出た）。`error` の記録で終わった回は `errors.jsonl` に入れ、`--resume` で回し直す。設計の失敗には数えない。
10. **出力先のディレクトリ名に LLM の名前を入れる**（`runs/<日時>-<LLM>/`）。3 つを同時に始めると日時が重なる。
11. **事前の確認に opencode を足す**。opencode の回は、`opencode` があるか、モデルが `opencode models` にあるかを、
    使用量を使う前に確かめる。`opencode models` は opencode のキャッシュ（ripgrep とモデルの一覧）も温める。空の
    キャッシュのまま回すと、最初の回はスキルが見つからないまま始まった。また空のキャッシュでは、1 回目の
    `opencode models` は opencode に同梱の古い一覧（DeepSeek も GLM もない）を返し、最新の一覧は次から返るので、
    見つからなければもう一度だけ聞く（どちらも計画のとき確かめた）。
12. **どのセッションも `PWD` を作業ディレクトリに合わせる**（計画のとき）。opencode は、プロセスの作業ディレクトリでは
    なく環境変数 `PWD` を作業場所にする（確かめた）。評価を起動した場所（リポジトリ）の `PWD` のまま回すと、試運転で
    DeepSeek も GLM も設計をリポジトリに書き、`cd` までした。`claude -p` と採点役も同じ関数で起動するので、すべての
    セッションで合わせる。

## スコープ外

- スキルを直すループ（状況確認の結果を見て決める。M5-2 の次の一歩）。
- 確かめ専用の新しい依頼（直す段で足す。今回は直さないので合わせ込みの心配がない）。
- OpenCode Go のキーの更新（ユーザー）と、有料版での評価。
- 採点役を opus 以外にすること。
- opencode 以外の道具（Codex など）。

## 設計

### 1. LLM の指定

```bash
make eval                       # sonnet（今までどおり）
make eval-full MODEL=deepseek   # opencode の無料版
make eval-full MODEL=glm
uv run python -m evals.design.run --model opencode/deepseek-v4.1-flash-free --cases plant-stand
```

- `--model` の値で道具を決める。`sonnet`・`opus`・`haiku` と `claude-` で始まる名前は Claude Code、短い名前
  （`deepseek`・`glm`）と `opencode/`・`opencode-go/` で始まる名前は opencode。それ以外は「使える名前」を挙げて止める。
- `meta.json` と結果の行には、指定した名前と、実際に動いたモデル（記録から取る）を残す。`--resume` は今までどおり
  `meta.json` の LLM で続ける。
- Makefile は `MODEL ?= sonnet` を `--model $(MODEL)` で渡す。

### 2. opencode で動かす

1 回ごとに、Claude Code の回と同じく、リポジトリの外の作業ディレクトリで動かす:

```bash
opencode run --format json --auto -m <モデル> "<依頼文>"
```

- 回ごとの opencode の設定ファイル（`opencode.json`）に、`skills.paths`（プラグインの写しの `skills/`）と断る道具を
  書き、作業ディレクトリの隣（エージェントからは見えない）に置く。
- 環境: Claude Code の回の環境（PATH・CLI の環境）に、`XDG_CONFIG_HOME`・`XDG_DATA_HOME`（作業ディレクトリの隣の
  一時ディレクトリ）と `OPENCODE_DISABLE_CLAUDE_CODE=1` を足す。
- 標準入力は `/dev/null`。時間切れと止め方（Ctrl-C）は Claude Code の回と同じ仕組み。

### 3. 記録の読み方

`opencode run --format json` は 1 行 1 イベントの記録を出す（確かめた）:

| イベント | 読むもの |
|---|---|
| `tool_use` | `part.tool` と `part.state.input`。`skill`（`name` が `design`）でスキルを読んだ、`bash`（`command`）で validate・render の回数と外の `/tmp`、`read`（`filePath` が `.png`）で画像を見た |
| `step_finish` | `part.tokens`（入力・出力・推論・キャッシュ）と `part.cost` を足す。数がターン数 |
| `error` | `error.data.message`。この回は失敗した試行 |
| 最初と最後のイベントの `timestamp` | 時間 |

Claude Code の回と同じ `Transcript` を作る。Claude Code の回のトークンは、最後の `result` の `usage` から取る。

### 4. スキルの直し

SKILL.md の「`${CLAUDE_PLUGIN_ROOT}/docs/dsl-specification.md`」を、SKILL.md からの相対リンク
（`[docs/dsl-specification.md](../../docs/dsl-specification.md)` のように、プラグインのルートの docs と分かる形）に
する。スキルの中で `${CLAUDE_PLUGIN_ROOT}` を使わないことを、テストで確かめる（今の「SKILL.md の中だけで使う」
というテストを置き換える）。

### 5. レポート

- 見出しの「Agent」に、指定した LLM と実際に動いたモデル、道具（Claude Code・opencode とその版）を出す。
- 「Spend per run」に入力・出力のトークン数（中央値と幅）を足す。依頼ごとの表にもトークンを足す。
- エージェントが答えを終えずに止まった回（opencode の最後のステップの理由が `stop` でないもの。`length` はモデルの
  出力の上限）は、回の行にその理由を出す。設計がないまま止まっても、仕組みの不調ではなくそのモデルで動くかどうかの
  結果なので、設計の失敗として数える（計画のとき。GLM の試運転が 4 ターン目に `length` で止まった）。
- 3 つの LLM を並べるのは、レポートを 3 つ並べて見る（チャットで並べて見せる）。1 つのレポートにまとめる仕組みは
  作らない（決定 1）。

## 状況確認（このあとに回す）

sonnet・`deepseek`・`glm` で、それぞれ `make eval-full`（10 件 × 3 回）を並列に回す。

- Claude の枠を使うのは、sonnet の設計（25〜30 USD 相当）と、3 つすべての採点（90 回 × 約 0.1 USD）で、合わせて
  35〜40 USD 相当の見込み。DeepSeek と GLM の設計は 0 円。
- 3 つを並列に回すと、同時に動くセッションは 6 つ（`--jobs 2` × 3）。無料版の受付が詰まって失敗が増えたら、
  `--resume` で続ける。
- 結果（合格率、依頼ごとの表、時間、トークン、画像）をチャットで並べて見せ、直し方をユーザーと決める。

## テスト

`make check` に入れる（LLM を呼ばない）:

- `--model` の振り分け: `sonnet` は Claude Code、`deepseek`・`glm` は opencode の無料版、`opencode/...` は
  そのまま、知らない名前は止まる。
- opencode のコマンドと環境: 切り離しの環境変数、設定ファイルの `skills.paths` と断る道具。
- opencode の記録の読み方: スキル・validate・render・画像・トークン・ターン・時間、`error` で終わった回は失敗した試行。
- 出力先のディレクトリ名に LLM の名前が入る。
- スキルの中に `${CLAUDE_PLUGIN_ROOT}` がない。SKILL.md の DSL 仕様へのリンクが実在する（今の `tests/test_docs.py`）。

## 完了条件

- `make check` が通る。最終レビュー（Opus）の指摘を直す。`make ci-local` が通る。
- `--self-check` が通る（採点役は変わらない）。`deepseek` と `glm` で 1 件ずつ試運転し、切り離し（読んだスキル、
  設定、記録の置き場所）と記録の読み方を確かめる。
- 状況確認の 3 つの `make eval-full` を回し、結果をチャットで並べて見せる。
