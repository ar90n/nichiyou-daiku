# R4a CLI の文字の出力（validate・report） 設計

- 日付: 2026-11-01
- ステータス: 設計（未実装）
- ブランチ: `next`（作業は `next-r4a-cli-text`）
- 親: `2026-10-29-next-generation-rust-core-design.md`（R4 CLI）

## 目的

Rust 版の CLI（実行ファイル `nichiyou-daiku`）を作り、まず文字を出すコマンド `validate` と `report` を Python 版と
同じ出力で移す。絵を出すコマンドと配り方は後の R4b・R4c。

## R4 の分け方（ユーザー承認）

R4 CLI は大きいので 3 つに分け、順に作る。

- **R4a 文字（この文書）**: CLI の骨組み、`validate`、`report`（木取りを含む）。絵の書き出しが要らず、Python 版と
  文字で突き合わせられる。
- **R4b 絵**: `render`（PNG）・`steps`・`drawing`（PDF）、`view`。R3 の描き方と PNG・PDF の書き出し。
- **R4c 配る**: プラグインの `bin/nichiyou-daiku` を Rust のビルド済みバイナリに替え、スキルと文書を合わせる。

設計ループ（エージェント）が使う `validate`・`render`・`report` を先にまとめる分け方は、R4a に PNG の書き出しと
確認用の図が入って大きくなるので選ばなかった。分けない案は、仕様が大きく計画の後半が圧縮後の文脈で進むので
選ばなかった。

## 決定と理由

1. **出力は Python 版と同じにし、正解ファイルで全件を突き合わせる**（ユーザー）。スキルや評価が読む形が変わらず、
   移し替えの間違いを機械的に捕まえられる。違ってよいのは `report` の生成日時と、定尺のファイルが TOML として
   読めないときの括弧の中の文（TOML を読む部品が書く文）だけ。中身の改善は移し終えてから別に決める。
2. **計算は core、文章は CLI のクレート**（ユーザー承認）。木取りと report の材料（部材の表・金物・ドリル・
   アンカーの詳細・下穴の位置・問題の文）は core に置き、ビューアー（WASM）も後で使えるようにする
   （C3 の仕様の「木取りは R4 の report で core に移す」）。全部を CLI に置く案は、ビューアーで木取りを使う
   ときに移し直すので選ばなかった。report 用のクレートを別に作る案は、今は Markdown をビューアーで出す予定が
   ないので重い。
3. **`validate --json` は文字まで同じにする**（キーの順、`indent=2`、数の書き方）。R1 は中身（値）で合わせ、
   キーの順を後回しにしていた。core の `serde_json` で `preserve_order` を有効にし、Python と同じ順でキーを入れる。
4. **core の依存は serde と serde_json のまま**。TOML の読み取り・引数・時刻は CLI のクレートに置く。CLI の
   外部のクレートは `clap`（引数）、`toml`（定尺のファイル）、`jiff`（生成日時を地元の時刻で書く）。
5. **色は端末に出すときだけ付ける**（click と同じ）。`-d`（traceback）は受け付けるが Rust には traceback が
   無いので何もしない。
6. **皿取りと部品図の題名の見せ方は R4a の後の小さな仕様にする**（ユーザー）。皿取り（皿ねじの頭が面にそろう
   ように穴の口を円すい形に削る）は下穴のデータ・部品図・3D・report を Python 版から変えるので、移し替えを
   確かめ終えてから Rust だけに入れる。そのとき下穴に関わる正解ファイルは Python から切り離し、Rust の出力を
   見直して新しい正解にする。部品図の題名（`leg_fl, leg_fr, leg_bl, leg_br ×4 2x4 750 φ2.5 ×12 φ10 ↧51 ×6`）
   は中身はそのままで、行を分けことばを足して読みやすくする（ユーザー）。皿取りが入ると題名の穴の行に
   皿取りも書くので、2 つを 1 つの仕様にまとめる。

## CLI の振る舞い（Python 版と同じ）

- `nichiyou-daiku [-d] [-v] [-q] <コマンド>`。R4a のコマンドは `validate` と `report`。
- 入力はファイルか `-`（標準入力）。読めないときは `Error: File not found: X`・`Error: Not a file: X`・
  `Error: Error reading file: …` を標準エラーに出し、終了コード 1。
- `validate`:
  - 文の出力: 読めたら `✓ DSL syntax is valid`、`-v` で部材と接続の数と部材の一覧、組み立てられて問題が
    無ければ `✓ Model is valid`。読めない・組み立てられないときは標準エラーに `✗ Syntax error`（Semantic・
    Validation・Unexpected・Assembly）、空行、本文。問題があれば `✗ Model has problems` と `  - …`。終了コード
    は問題・エラーで 1。
  - `--json`: R1 の JSON を文字まで同じに（決定 3）。`-q` でも出す。
- `report`:
  - オプション: `-o`、`--project-name`（既定 `Woodworking Project`）、`--include-cut-diagram/--no-cut-diagram`、
    `--include-anchor-details/--no-anchor-details`、`--include-pilot-holes/--no-pilot-holes`、`--stock`。
  - 節: 概要（生成日時は地元の時刻 `%Y-%m-%d %H:%M`）、問題があれば Warnings、材料表、アンカーの詳細、下穴と
    面の文字の図、買い物リスト（材・金物・ドリル）、定尺からの買い方、木取りの図。
  - `-o` では標準エラーに `Report written to: X`（`-q` で出さない）。
  - 定尺のファイルは最初に読み、誤りは Python と同じ文で止まる（決定 1 の例外を除く）。

## 組み立て

### core（`crates/nichiyou-daiku-core`）

- `cutting.rs`（新規）: `shell/cutting.py` を移す。長い順に詰める詰め方（`_fill_boards`）を定尺の組み合わせ
  ごとに試し（8 種類まではすべての組み合わせ、それより多ければ全部と 1 種類ずつ）、買う長さの合計、次に枚数が
  いちばん少ないものを選ぶ。どの定尺より長い部材は別に出す。既定の定尺（1820・2440・3050・3650mm）と
  のこの刃の幅 3mm。
- `resources.rs`（新規）: `shell/resources.py` を移す。部材の表、種類ごとの数と長さ、金物の数、ドリルの径と
  最も深い穴、アンカーの詳細、下穴の位置（面から測った距離）、問題の文。今ある `hardware.rs`・`parts.rs`・
  `diagnostics.rs` を使う。
- `serde_json` の `preserve_order` を有効にし、`validate` の JSON のキーを Python と同じ順で入れる。数の書き方は
  `pyfmt` でそろえる。

### CLI（`crates/nichiyou-daiku-cli`、新規、実行ファイル `nichiyou-daiku`）

- `main.rs`: `clap` で全体のオプションとコマンドを読む。
- `echo.rs`: 標準出力・標準エラーへの出し方（`-q`・`-v`、端末のときだけ色）。
- `input.rs`: ファイルか標準入力を読み、読めないときの文。
- `validate.rs`・`report.rs`: コマンド。
- `markdown.rs`: report の各節を `shell/report_generator.py` と同じ順・同じ書式で組む（`pyfmt` を使う）。
- `stock.rs`: `toml` で定尺のファイルを読み、Python と同じ確かめ方と文（`shell/stock.py`）。

`make check` と CI の Rust の検査は、ワークスペースにクレートを足すことで CLI も含む。

## テスト

- 正解ファイル（`tools/make_goldens.py` を広げ、今の 769 件の隣に書く）:
  - `NAME.validate.txt`: `validate` の文の出力（標準出力・標準エラー・終了コード、色なし）。全件。
  - `NAME.validate.json`: R1 からの `validate --json` の出力を、文字まで同じかで比べる。
  - `NAME.report.md`: 組み立てられる 671 件の `report`（既定のオプション）。生成日時の行は比べる前に両方とも
    決まった文に置き換える。
  - Python の出力が実行ごとにぶれないことを、`PYTHONHASHSEED` を変えて 2 回作って確かめる。
- オプションの組み合わせ（ワゴンなどいくつかの例）: 図の有無の 3 つの切り替え、`--project-name`、定尺の TOML
  （正しいもの 1 つと、誤りの文が出るもの一通り。TOML として読めないときの括弧の中は比べない）、`-o`、`-q`、`-v`。
- 単体テスト: 木取り（Python の doctest の例と定尺の組み合わせを選ぶ場面）、定尺のファイルの確かめ、端末の
  ときだけ色が付くこと。
- CLI のテストはビルドした実行ファイルを `std::process::Command` で動かし、出力をまるごと比べる。
- 正解ファイルの増える量を測ってこの文書に書く（今のコーパスは 20MB）。

## R4a で作らないもの

`render`・`drawing`・`steps`・`view`（R4b）、配り方（R4c）、`export`（R5）、皿取りと部品図の題名の見せ方
（R4a の後の小さな仕様、決定 6）。

## R4a が終わる条件

- 正解ファイルとすべて一致し、`make check` と `make ci-local` が通る。
- ユーザーが `cargo run -p nichiyou-daiku-cli -- report …` でワゴンの report を出し、Python 版と見比べて確かめた。
