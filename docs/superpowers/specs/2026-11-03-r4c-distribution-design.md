# R4c 配る（ビルド済みの実行ファイルと view） 設計

- 日付: 2026-11-03
- ステータス: 設計（未実装）
- ブランチ: `next`（作業は `next-r4c-distribution`）
- 親: `2026-10-29-next-generation-rust-core-design.md`（R4 の分け方）、`2026-11-02-r4b1-render-and-steps-design.md`（`view` を R4c に回した）

## 目的

Rust 版の CLI を、Python・uv・build123d 無しで使えるように配る仕組みを作る。GitHub Actions で各 OS の実行ファイルを
ビルドして Releases に置き、プラグインの `bin/nichiyou-daiku` はそれを落として動かす。あわせて `view` を、CLI に
入れたブラウザのビューアーで `.nd` を開く形で作る。

プラグイン: このリポジトリは Claude Code のプラグインでもあり（`.claude-plugin/`、`skills/design/`、`bin/nichiyou-daiku`）、
`/plugin install` した人の Claude Code で設計スキルと CLI が使える。`bin/nichiyou-daiku` が CLI の入口。

## 決定と理由

1. **利用者に Rust 版を届けるのは R6（Python を消すとき）**（ユーザー）。R4c では仕組みを `next` に作るだけで、`main`
   （プラグインの配り元）は変えない。届ける前に R5 で `export` も Rust になるので、入口に Python へ回す道は作らない。
   R4c の後すぐ届ける案（`export` だけ Python に回す）と R5 の後に届ける案は選ばなかった。
2. **実行ファイルは GitHub Actions でビルドし、Releases に置く**（ユーザー）。入口は初回に同じ版のものを落として
   キャッシュに置く。使う人に Rust の道具一式は要らず、初回も数秒で済む。初回にソースからビルドする案は使う人に Rust が
   要り数分かかるので、実行ファイルをリポジトリに入れる案は版ごとに数 MB × OS の数が git の履歴にたまるので選ばなかった。
3. **リリースは下書きで置き、公開はメンテナーが押す**。Releases に置いたものはプラグインの入口がすぐ落とすので、中身を
   確かめてから公開できるようにする。
4. **`view` はビューアーを CLI に入れ、手元の小さなサーバーで `.nd` と一緒に配信する**（ユーザー）。ネットにつながらなく
   ても動き、CLI とビューアーの版が必ず合う。GitHub Pages のビューアーを `?src=` で開く案は、Pages を公開しておく
   必要があり、https のページから localhost を読む制限（ブラウザによっては拒む）と版のずれがあるので選ばなかった。
5. **保存したら画面が変わる**。`view` の開く URL に `&watch` を付け、ビューアーは 1 秒ごとに `.nd` を読み直して、中身が
   変わったときだけ開き直す（タブ・手順・視点はそのまま）。エージェントが `.nd` を直すたびに人が見直せる。サーバーから
   知らせる仕組み（SSE など）は、読み直しで足りるので作らない。
6. **ビューアーは、ビルドのときに `web/dist` があれば組み込む**。無ければ組み込まず、`view` は理由と直し方を言って止まる。
   `cargo build` だけの開発やソースからのビルドで npm を要らなくするため。リリースのビルドは必ず先にビューアーを作る。

## リリースのビルド（`.github/workflows/release.yml`）

- 動く時: `v*` のタグの push（作って下書きのリリースに置く）と、手で動かす `workflow_dispatch`（作るだけ。成果物は
  Actions の artifact）。
- ビューアー: 1 つのジョブで WASM と画面をビルドし（`make web`）、`web/dist` を artifact にする。
- 実行ファイル（ビューアーを組み込む）: 次の 5 つ。各ジョブは `web/dist` を受け取り、
  `cargo build --release -p nichiyou-daiku-cli --target <target>` でビルドし、例の `.nd` を `validate` して動くことを確かめ、
  `nichiyou-daiku-<版>-<target>.tar.gz`（Windows は `.zip`。中身は `nichiyou-daiku` か `nichiyou-daiku.exe`）にまとめる。
  - `x86_64-unknown-linux-musl`・`aarch64-unknown-linux-musl`（静的リンク、どのディストリでも動く）
  - `aarch64-apple-darwin`・`x86_64-apple-darwin`
  - `x86_64-pc-windows-msvc`
- リリース（タグのときだけ）: タグ（`v0.2.0`）と `Cargo.toml` の `[workspace.package]` の版（`0.2.0`）が違えば止める。
  全部の成果物と `SHA256SUMS`（`sha256sum` の形）を下書きのリリースに置く。
- 今の CI（Dagger、`ci.yml`）とビューアーの公開（`pages.yml`）は変えない。

## プラグインの入口（`bin/nichiyou-daiku`）

POSIX の sh のまま、Python を動かす部分を消し、次の順に探して `exec` する。

1. PATH にほかの `nichiyou-daiku` があれば使う（今と同じ。`NICHIYOU_DAIKU_WRAPPED` で入口どうしが呼び合わない）。
2. キャッシュ `${XDG_CACHE_HOME:-$HOME/.cache}/nichiyou-daiku/<版>/nichiyou-daiku`（Windows は `.exe`）があれば使う。
   版はプラグインの `Cargo.toml` の `[workspace.package]` の `version`。
3. 落とす: `uname -s`・`uname -m` から target を決め（Linux・Darwin・MINGW/MSYS/CYGWIN、x86_64/amd64・aarch64/arm64）、
   `${NICHIYOU_DAIKU_RELEASES:-https://github.com/ar90n/nichiyou-daiku/releases/download}/v<版>/` から成果物と
   `SHA256SUMS` を `curl`（無ければ `wget`）で落とす。`sha256sum`（無ければ `shasum -a 256`）で確かめ、一時フォルダに
   開いてからキャッシュに移す（途中で止まっても壊れたものを置かない）。標準エラーに
   `nichiyou-daiku: downloaded v<版> for <target>` を 1 行出す。
4. 作る: 落とせず `cargo` があれば、プラグインのソースから `cargo build --release -p nichiyou-daiku-cli`（ビルドの
   置き場はキャッシュの中）で作ってキャッシュに置く。このときビューアーは入らない（決定 6）。
5. どれも無ければ、何が無くどうすればよいかを言って 127 で終わる:
   `nichiyou-daiku: could not download v<版> for <target> (<理由>), and cargo is not installed to build it.` に続けて、
   Releases のページから手で落として PATH に置くか、Rust（https://rustup.rs）を入れて同じコマンドをもう一度、と書く。
   知らない OS・CPU は、その名前を言って同じく止める。

`NICHIYOU_DAIKU_RELEASES` は落とす元を差し替える（テストで `file://` の偽のリリースを使う、ミラーを使う）。

## view

- CLI: `view FILE [--host HOST] [--port N] [--no-open]`。`--host` の既定は `127.0.0.1`、`--port` の既定は 0（空いている
  ものを使う）。
- 手元に HTTP サーバー（`tiny_http`）を立て、次だけを配信する。ほかのパスは 404。
  - `/`・`/index.html` と `/assets/…`: 組み込んだビューアー（`web/dist`）。種類（MIME）は拡張子から（`.html`・`.js`・
    `.css`・`.wasm`・`.svg`・`.png`）。
  - `/<ファイル名>`: その `.nd` を毎回読み直して返す（`Cache-Control: no-store`）。標準入力 `-` のときは読んだもの
    （名前は `stdin.nd`）を返し、`&watch` は付けない。
- 立てたら標準エラーに `Viewing <ファイル名> at <URL> (Ctrl-C to stop)` を出し、ブラウザで開く（Linux は `xdg-open`、
  macOS は `open`、Windows は `cmd /c start`）。`--no-open` のとき、または `--host` が `127.0.0.1`・`localhost`・`::1`
  でないときは開かない。開けなかったときは `Open <URL> in a browser` と出して続ける。URL は
  `http://<host>:<port>/?src=<ファイル名>&watch`（ファイル名はパーセント符号化する。`--host` が `0.0.0.0` なら、その機械の名前ではなく `0.0.0.0` のまま
  出し、別の機械からはその機械のアドレスで開くよう一言添える）。
- `.nd` が読めない（無い）ときは、立てる前に `Error: File not found: …` で止まる（`validate` と同じ文）。立てた後に
  消えたら 404 を返し、ビューアーがその旨を出す。
- ビューアーを組み込んでいないとき: `Error: This nichiyou-daiku was built without the viewer: build the viewer
  (make web), then build the CLI again`。
- ビューアーの変更（`web/src`）: `?src=` に `&watch` があれば、1 秒ごとに `src` を `cache: "no-store"` で読み直し、
  中身が前と違うときだけ開き直す。開き直してもタブ・手順・視点はそのまま。読めないときは前の表示のまま、次の読み直しを
  待つ。
- `build.rs`: `../../web/dist/index.html` があれば `web/dist` の全ファイルを組み込む表を作る。無ければ空の表。
  `web/dist` の変化でビルドし直す。

## テスト

- 入口: Rust のテスト（`crates/nichiyou-daiku-cli/tests/plugin_bin.rs`）が `sh bin/nichiyou-daiku` を、偽の PATH・
  キャッシュ・`NICHIYOU_DAIKU_RELEASES=file://…` の偽のリリースで動かす。PATH のものを優先する、落としてキャッシュに置き
  2 回目は落とさない、チェックサムが合わなければ置かずに止まる、知らない OS では止まる（`uname` を偽物にする）。
- view: CLI のテストで `view --no-open --port 0` を動かし、出した URL から `index.html` と `.nd` が取れる、`.nd` を
  書き換えると新しい中身が返る、ほかのパスは 404、無いファイルは立てる前に止まる。ビューアーを組み込まないビルドの文。
- ビューアー: vitest で、`&watch` があると読み直し、中身が変わったときだけ開き直す。
- リリースのビルド: `next-r4c-distribution` を push して `workflow_dispatch` で動かし、5 つの成果物ができることを
  確かめる（push と実行はユーザーに頼んでから）。
- 見た目: ユーザーが `view` をブラウザ（Tailscale 経由）で開き、`.nd` を保存すると変わることを確かめる。

## R4c で作らないもの

利用者に届けること（`main` に入れる、R6）、README・設計スキルの入れ方の説明の書き換え（R6）、`export`（R5）、
Python へ回す道、パッケージマネージャー（Homebrew など）への登録、実行ファイルの署名。

## R4c が終わる条件

- 上のテストがすべて通り、`make check` と `make ci-local` が通る。
- リリースのワークフローを手で動かして 5 つの成果物ができた。
- ユーザーが `view` を見て確かめた。
