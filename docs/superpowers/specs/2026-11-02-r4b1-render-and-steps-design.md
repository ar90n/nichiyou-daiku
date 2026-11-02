# R4b1 CLI の render と steps（PNG） 設計

- 日付: 2026-11-02
- ステータス: 設計（未実装）
- ブランチ: `next`（作業は `next-r4b1-render-steps`）
- 親: `2026-11-01-r4a-cli-text-design.md`（R4 の分け方）、`2026-11-01-r3c1-part-drawings-design.md`・
  `2026-11-01-r3c2-step-drawings-design.md`（部品図・手順の図）

## 目的

Rust 版の CLI に、絵を出すコマンドのうち `render`（設計ループの確認用の PNG）と `steps`（組み立ての手順の
`steps.md` と PNG）を作る。SVG を PNG にする土台もここで作る。

## R4b の分け方（ユーザー承認）

- **R4b1（この文書）**: PNG にする土台、`render`、`steps`。設計ループが使う `render` が先にそろう。
- **R4b2**: `drawing`（PDF の図面）。
- **`view`**: R4c（配る）で、ブラウザのビューアーを開く形にする。Python 版の `view` は外の 3D の窓（ocp-vscode・
  jupyter-cadquery）に頼るので、そのまま移せない。

コマンドごとに 4 つに分ける案は仕様と計画の往復が増え、分けない案は大きくなりすぎるので選ばなかった。

## 決定と理由

1. **PNG は resvg で作り、DejaVu Sans（標準と太字）を実行ファイルに組み込む**（ユーザー承認）。エージェントが
   読む絵がどの機械でも同じになり、Python 版が要った cairo も要らなくなる。実行ファイルは 1.5MB ほど大きくなる。
   機械の字体を使う案は、字体の無い機械（Mac など）で測った幅とずれるので選ばなかった。SVG だけを書く案は、
   エージェントが絵として読めず設計ループが壊れるので選ばなかった。
2. **resvg は CLI のクレートだけで使う**。core・描き方のクレート・WASM には入れず、ビューアーの WASM は
   大きくならない。
3. **`render` は Python 版と同じ組み方と CLI にする**。角を丸めない箱で描く（C2 と同じ）ので、
   `--fillet-radius` は受け付けるが使わない（今までの使い方が壊れないように）。
4. **`steps` は Python 版と同じ出力先・ファイル名・`steps.md`・メッセージにする**。画像は C1 の部品図と C2 の
   手順の図（SVG）を PNG にしたもの。
5. **正解ファイルは Python とのつながりを残す**。`steps.md` は、穴を Python の形に戻した組み立て
   （`tests/common::python_holes`）から作って Python の正解と全件比べる（皿取りで部品のまとまりが変わる分も
   戻るので、違ってよいものは無い）。`render` は、名前の付いた部材・名前の出なかった部材・注記の文を、例と
   文書の例について Python の正解と比べる（Python は build123d の隠れ線で遅いので例に絞る）。

## render

- CLI: `render FILE [-o PATH] [--size N] [--fillet-radius R]`。既定の出力は `<入力>.png`（標準入力 `-` のときは
  `-o` が要る）。`--size` は 1 辺の px（既定 1400）。成功で `Successfully rendered: PATH`、組み立ての問題は
  `Warning: …`（文は Python と同じ）。
- 組み方（Python の `shell/render.py: render_sheet` のまま）:
  - 正方形を 2×2 に分け、左上 `from +z`（上は −y）、右上 `from -x +y +z`、左下 `from +y`、右下 `from -x`
    （上は z）。余白と見出しの帯は 1 辺の 4%。
  - 4 つの図は同じ縮尺で、いちばん大きい図が枠の 9 割に入る。線は見える線だけで、C2 の箱どうしの隠れ線
    （`hidden.rs`）を使い、穴も描く。線の太さは max(1, size/1000) px。
  - 部材名は、中心と見る側の間にほかの部材が無い部材だけに、中心に赤（`#b00000`）で置き、ほかの名前の箱
    （幅は 1 文字 0.6 × 字の大きさ）と重なるものは省く。字の大きさは max(10, size/80)、見出しは
    max(12, size/50)、注記は max(10, size/60)。文字には白い縁取り。
  - 下の注記: `<題名> W x D x H mm (x × y × z)`（つながっていなければ `<題名>  pieces not connected`）と、
    どの図にも名前の出なかった部材の一覧（`not labelled: …`、収まらなければ `(+N more)`、それも入らなければ
    `not labelled: N pieces`）。行の幅は文字数で決める（Python の `textwrap` と同じ折り返し）。
- 描き方のクレートに `render_sheet`（SVG と、名前・注記などの中身）を置く。

## steps

- CLI: `steps FILE [-o DIR] [--size N] [--fillet-radius R]`。既定の出力先は `<入力>-steps/`、画像の幅は既定
  1600px。標準入力のときは `-o` が要り、`-o` がファイルなら `<DIR> is a file; give -o a directory for the steps` で
  止める。題名は入力のファイル名（拡張子なし）、標準入力ならフォルダの名前。
- 書くもの: 穴のある部品ごとの `part-NN.png`、手順ごとの `step-NN.png`（番号の桁は数に合わせる、Python と同じ）、
  `steps.md`。前の実行で残った、今回の数より多い番号の画像は消す。
- `steps.md`（Python の `steps_markdown` のまま）: `# <題名>: assembly steps`、手順の分け方の助言（あれば）、
  部品表と部品図、手順ごとの `## 見出し`・画像・部材の表・金物の表。
- メッセージ: 助言、入りきらない数値の `Warning: …`、最後に
  `Successfully wrote steps.md, N part drawings and M step images to DIR`（Python と同じ文）。

## PNG

- CLI のクレートの `png.rs`: SVG を resvg で幅 N px の PNG にする（高さは縦横比のまま、背景は白）。
- 字体: `crates/nichiyou-daiku-cli/fonts/` に DejaVu Sans（Book・Bold）と利用許諾の文書を置き、
  `include_bytes!` で組み込む。SVG の `font-family` に DejaVu Sans を書いてあるので、それが使われる。

## テスト

- `steps.md`: `tools/make_goldens.py --cli` で組み立てられる 671 件の Python の `steps.md`（題名は固定の文）を
  書き、Rust は `python_holes` で穴を戻した組み立てから作って全件を文字まで比べる。
- `render`: 例と文書の例（`example-*`・`doc-*`）について、Python の `render_sheet` の図ごとの名前の付いた部材、
  名前の出なかった部材、注記の文を正解ファイルにして比べる。
- PNG: できた PNG が読め、幅が `--size` のとおり。組み込みの字体で文字が描かれる（文字の場所に黒い画素がある）。
- CLI: 出力先の決まり（既定の名前、標準入力の `-o`、`-o` がファイル）、メッセージ、残った画像を消すこと、番号の桁。
- 見た目: ファイルワゴンの `render` と `steps` の画像をユーザーが Python 版と見比べて確かめる。

## R4b1 で作らないもの

`drawing`（R4b2）、`view` と配り方（R4c）、角を丸めた描き方。

## R4b1 が終わる条件

- 上のテストがすべて通り、`make check` と `make ci-local` が通る。
- 字体の利用許諾の文書が入っている。
- ユーザーが画像を見て確かめた。

実行ファイル（リリースビルド、Linux x86_64）は 6.0MB になった（組み込んだ字体 1.4MB を含む）。ファイルワゴンの `steps` は 1.8 秒、`render` は 0.3 秒（Python 版は `steps` に 30 秒）。
