# R6 Python 版を消して Rust 版を届ける 設計

- 日付: 2026-11-04
- ステータス: 設計（未実装）
- ブランチ: `next`（作業は `next-r6`）
- 親: `2026-10-29-next-generation-rust-core-design.md`（R6 の片付け、評価は Python のまま）、`2026-11-03-r4c-distribution-design.md`（配る仕組み、届けるのは R6）

## 目的

製品の Python のコードを消し、Rust 版を利用者（Claude Code のプラグインと CLI）に届けて、main を第 2 世代にする。
Python を消した後は Rust 版の出力が正解になる。

## 決定と理由

1. **CLI だけ使う人には、入れるスクリプト（`install.sh`）を用意する**（ユーザー）。`curl … | sh` でその OS の実行
   ファイルを Releases から落とし、SHA256SUMS で確かめて置く。Rust も uv も要らない。Releases から手で落とすだけの
   案は使う人の手間が増え、`cargo install` を足す案はビューアーが組み込まれず `view` が使えないので選ばなかった。
   Windows は Releases から手で落とす（スクリプトは作らない）。
2. **Python 版はタグ `v0.1.0` で残す**（ユーザー）。main を入れ替える前の最後の Python 版に付け、README に Python API が
   要る人向けの入れ方を 1 行書く。手入れはしない。
3. **プラグインの入口はプラグイン自身の版だけを使う**（ユーザー）。PATH を見ない。`uv tool install` で入れた古い
   Python 版が PATH にあっても動かず、スキルの説明と CLI の版が必ず合う。開発と評価では `NICHIYOU_DAIKU_BIN` で
   手元のビルドに差し替える。版が合うときだけ PATH を使う案は仕組みが複雑で、PATH 優先のまま案内だけする案は
   古い版を消し忘れると古い版が動くので選ばなかった。
4. **正解ファイルはすべて Rust の出力で一度書き直し、完全一致で比べる**（ユーザー承認）。`ND_BLESS=1 cargo test` で
   書き直し、動きを変えたときは書き直した差分をレビューする。Python の形に直して比べる道具は消える。中身が Python
   版と一致することは R1〜R5 で確かめ済みなので、失うものは無い。Python の正解ファイルを凍結して Python の形で
   書き直す仕組みを足す案は、Python の形への変換を持ち続けるので選ばなかった。
5. **CI の Dagger のパイプラインは開発の道具として Python のまま残す**（ユーザー承認）。中身を Rust・web の検査と、
   評価と道具の Python の lint にする。`make ci-local` で手元でも CI と同じことを確かめられる形を保つ。GitHub
   Actions に cargo と npm を直に書く案は、手元で CI を試す手段が無くなるので選ばなかった。
6. **評価（`evals/design`）は Python のまま、設計の確かめは CLI の `validate --json` で行う**（親の仕様の決定 6）。
   評価が Python のライブラリを読まなくなるように、`validate --json` に接続の種類（`connections`）と手順の数
   （`steps`）を足す。設計スキルのエージェントにも役立つ。
7. **CLI に `--version` を足す**。インストールのスクリプトが古い Python 版（`--version` に答えない）を見分け、利用者が
   版を確かめるのに使う。
8. **リリースを公開してから main を動かす**。プラグインの入口は自分の版のリリースが無いと CLI を落とせないので、
   main を先に動かすと、その間にプラグインを更新した人の CLI が動かない。

## 正解ファイルとテスト

- 11 種類（`validate.json`・`holes.json`・`steps.json`・`parts.json`・`chains.json`・`cli-validate.txt`・
  `cli-report.txt`・`cli-validate-json.txt`・`steps.md`・`render.json`・`solids.json`）を Rust の出力で書き直す。
  件数と対象の .nd は今と同じ。比べ方は完全一致で、置き換えるのは report の日付だけ。
- `ND_BLESS=1 cargo test` で、そのテストが比べる正解ファイルを出力で書き直す（今 report だけにある仕組みを全種類に
  広げる）。新しい例は .nd をコーパスに置いて同じように正解を作る。
- 消すもの: `python_holes`、構文エラーの文を分けて比べる仕組み（`DESCRIPTIONS`・`HINTS`・`split_syntax`）、UUID の
  付け替え（Rust の名無しの部材の ID は `00000000-0000-4000-8000-…` と決まっている）、`tools/make_goldens.py`、
  `tools/capture_dsl.py`。
- ドキュメントとプラグインのテストを Rust に移す（`crates/nichiyou-daiku-cli/tests/docs.rs`・`plugin.rs`）。
  - 引き継ぐ: 文書（`docs/`・README・`skills/`）の `.nd` のコードブロックと例の `.nd` が通る、すべての `.nd` の
    ブロックを拾えている、材種の表とプリセットの表がコードと合う、stock.toml の例が書いたとおりに読める、相対リンクと
    文書に書いたリポジトリのパスが在る、`validate --json` の例が CLI の出力と合う、すべてのコマンドが文書にある、
    プラグインの manifest と marketplace、スキルの決まりごと（frontmatter、仕様を読む範囲、`CLAUDE_PLUGIN_ROOT` に
    頼らない、CLI が落とせないときの案内）。
  - 移さない: Python API の例のテスト（API ごと消える）。

## Python を消すものと残すもの

- 消す: `src/`、`tests/`、`examples/*.py`、`docs/api-specification.md`、`.github/workflows/release-drafter.yml`
  （リリースは `release.yml` が下書きを作る）、codecov への送信。
- 開発の道具として Python で残す:
  - `evals/design`: `checks.py` は `nichiyou-daiku validate --json` の出力で確かめる。評価で動かす CLI は
    `NICHIYOU_DAIKU_BIN`（無ければプラグインの入口）。
  - `ci/dagger_pipeline.py`: Rust（fmt・clippy・test・WASM のビルド）、web（型・テスト・ビルド）、評価と道具の
    lint（ruff・pyright）。
  - `tools/check_step.py`: 部材名を `validate --json` から取る。build123d はそのときだけ（`uv run --with build123d`）。
- `pyproject.toml` はパッケージではなくし（`[tool.uv] package = false`）、評価と CI の依存だけを持つ。
- `Makefile`: `check` は `rust-check`・`web-check` と評価・道具の lint。`test`（pytest）は消し、`format` は ruff
  （評価・道具）と cargo fmt。

## CLI に足すもの

- `--version`: `nichiyou-daiku 0.2.0` を出して 0 で終わる。
- `validate --json` に 2 つ:
  - `connections`: 接続ごとに `{"base": …, "target": …, "type": "vanilla" | "dowel" | "screw"}`、宣言の順。
  - `steps`: 宣言した手順の数。手順のブロックが無ければ 0。
  - 構文や意味のエラーで設計を読めないとき（`error` があるとき）は `connections` は空、`steps` は 0。
  - DSL 仕様の `--json` の説明と例を直す。

## 入口とインストール

- プラグインの入口 `bin/nichiyou-daiku`:
  - `NICHIYOU_DAIKU_BIN` があればそれを動かす。
  - 無ければプラグインと同じ版（`Cargo.toml` の版）を、キャッシュ（`~/.cache/nichiyou-daiku/<版>`）→ Releases から
    落とす → ソースからビルド（cargo があるとき）→ 案内、の順に使う。PATH は見ない。
  - 落とす部分は `install.sh` と共通にし、入口は `sh "$root/install.sh" --version <版> --to <キャッシュ>` を呼ぶ。
- `install.sh`（リポジトリの直下、POSIX sh）:
  - 使い方は `curl -fsSL https://raw.githubusercontent.com/ar90n/nichiyou-daiku/main/install.sh | sh`。
  - 版: 最新のリリース（`/releases/latest` の転送先のタグ）。`--version` か `NICHIYOU_DAIKU_VERSION` で指定できる。
  - 置き場所: `~/.local/bin`。`--to` か `NICHIYOU_DAIKU_INSTALL_DIR` で変える。
  - OS とアーキテクチャから target を決め、アーカイブと SHA256SUMS を落とし、合えば置く。合わなければ置かずに止まる。
  - 置き場所が PATH に無ければ足し方を言う。PATH に `--version` に答えない `nichiyou-daiku`（古い Python 版）があれば
    `uv tool uninstall nichiyou-daiku` を案内する。
  - 知らない OS・アーキテクチャでは理由と Releases のページを言って止まる。
  - 落とす先は `NICHIYOU_DAIKU_RELEASES` で差し替えられる（テスト用、今の入口と同じ）。

## ドキュメント

- README: Python と codecov のバッジ、`uv tool install` の説明、「Typed Python API」、「(needs the viz extra)」を消す。
  インストールは `install.sh`、Windows は Releases から手で、ソースから（cargo と `make web`）。プラグインの節は
  初回に CLI を落とす（数秒）。ビューアーの節は `nichiyou-daiku view` を中心にし、Pages での公開を書き添える。
  Python API が要る人は `uv tool install "git+https://github.com/ar90n/nichiyou-daiku@v0.1.0"`。
- `docs/dsl-specification.md`（英語、正本）: CLI の節を Rust 版に合わせる（「requires build123d」を消す、`view` は
  ブラウザのビューアー、`export` は角を丸めず `--fillet-radius` は受けるが使わない、`--version`、`validate --json` の
  `connections` と `steps`、API 仕様へのリンクを消す）。
- `skills/design/SKILL.md`: `uv tool install --force` で入れ直す案内と「初回は build123d を入れるので数分」を消し、
  CLI が落とせないときの案内（入口が言う文に沿う）に替える。
- `evals/design/README.md`: `NICHIYOU_DAIKU_BIN` で手元のビルドを使うことを書く。
- CLAUDE.md（git 管理外）: Rust 版に書き直す（コマンド、`crates/` の構成と責務、設計の原則、worktree の決まり）。
- 過去の仕様（`docs/superpowers/specs/`）は経緯の記録なのでそのままにする。

## 届ける手順

タグ・リリース・main の push は、その都度ユーザーに頼んでから行う。

1. R6 を `next-r6` で作り、レビュー・`make ci-local`・ユーザーの確認を経て `next` に入れる。
2. main の最後の Python 版（`6868f53`）にタグ `v0.1.0` を付けて push する。
3. `next` の先頭にタグ `v0.2.0` を付けて push する。`release.yml` が 5 つの target の実行ファイルと SHA256SUMS を
   下書きのリリースに置き、ユーザーが中身を確かめて公開する。
4. 公開されたリリースで、`install.sh` で入れる・空のキャッシュでプラグインの入口を動かすことを確かめる。
5. main を `next` に早送りして push する（main は `next` の祖先）。main の CI が新しいパイプラインで通ることを確かめる。
6. 以後は main で開発する。リモートの `next` と `next-r4c-distribution` はユーザーが消す。

## テスト

- 正解ファイル: 書き直した後、全テストが完全一致で通る。`ND_BLESS=1` で書き直しても差分が出ない。
- ドキュメントとプラグイン: 上の「引き継ぐ」すべて。
- CLI: `--version` の出力、`validate --json` の `connections`（3 種類と宣言の順）と `steps`（ブロックありと無し、
  組み立てられないとき）。
- 入口（偽の curl と uname、今の `plugin_bin.rs` と同じ）: 同じ版のキャッシュを使う、無ければ落とす、PATH の古い
  `nichiyou-daiku` を使わない、`NICHIYOU_DAIKU_BIN` を動かす。
- `install.sh`: 最新の版を読んで置く、版の指定、チェックサムの不一致で置かない、知らない OS、PATH に無いときの案内、
  古い Python 版の案内。
- 評価: `--self-check` が新しい `checks.py` で通る（既知の設計で判定が変わらない）。
- 道具: `tools/check_step.py` が例のすべてで通る（`uv run --with build123d`）。

## R6 で作らないもの

Homebrew などのパッケージマネージャーへの登録、実行ファイルの署名、Windows 向けのインストールのスクリプト、Python 版の
手入れ、評価を Rust で書き直すこと、crates.io への公開。

## R6 が終わる条件

- 上のテストがすべて通り、`make check` と `make ci-local` が通る。
- `v0.2.0` のリリースが公開され、`install.sh` とプラグインの入口でそれが動く。
- main が Rust 版になり、main の CI が通る。
