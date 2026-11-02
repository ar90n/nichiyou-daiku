# R4b2 CLI の drawing（PDF の図面） 設計

- 日付: 2026-11-02
- ステータス: 設計（未実装）
- ブランチ: `next`（作業は `next-r4b2-drawing`）
- 親: `2026-11-02-r4b1-render-and-steps-design.md`（R4b の分け方、PNG の土台）、
  `2026-10-17-front-view-design.md`（図の向き）

## 目的

Rust 版の CLI に `drawing` を作る。家具全体の図面を PDF（または SVG）で出す。平面図・正面図・右側面図・立体図、
全体の大きさと部材の位置の寸法、表題欄を 1 枚の紙に描く。

## 決定と理由

1. **表題欄は部品図と同じ「属性: 値」の簡素な形にし、区画の記号（A〜F・1〜4）は付けない**（ユーザー）。部品図・手順の図と
   同じ書き方で読め、1 枚の家具の図面に区画の記号は要らない。Python 版（build123d の `TechnicalDrawing`）の見た目に近づける案は
   選ばなかった。
2. **隠れ線は正投影の 3 図（平面図・正面図・右側面図）だけに描き、立体図は見える線だけにする**（ユーザー）。正投影図では中の穴や
   部材の重なりが分かり、立体図は形をつかみやすくなる。手順の図（2026-10-17）と同じ考え方。4 つすべてに描く案（Python 版）は
   立体図が線でごちゃごちゃするので、どれにも描かない案は部材の裏の穴が図面から分からなくなるので選ばなかった。
3. **紙を広く使う**（ユーザー）。枠の余白は JIS に合わせ A4・A3 は 10mm、A2・A1 は 20mm、表題欄は中身の大きさにする。図を描ける
   場所が広がり縮尺が大きくなる。Python 版と縮尺・配置は変わるので、突き合わせるのは寸法の中身（決定 5）にする。Python 版と同じ
   枠の大きさにする案は、縮尺まで突き合わせられるが表題欄が大きく（A3 で 195×65mm）空きが多いので選ばなかった。
4. **PDF は図の SVG を svg2pdf 0.13 で作り、resvg を 0.49 から 0.45 に下げて SVG の読み込み（usvg 0.45）を PNG と共有する**
   （ユーザー）。文字は文字のまま、使った字だけ DejaVu Sans を埋め込むので、PDF の中で選べて検索できる（試しで確認: 部品図の
   PDF 37KB、字体は部分埋め込み）。resvg 0.49 のまま svg2pdf を足す案は usvg が 2 つ入り実行ファイルが大きくなるので、PDF を
   pdf-writer で自分で書く案は文字を選べずコードが大きく増えるので選ばなかった。
5. **正解ファイルは寸法の中身を Python とつなぐ**。図面の直列寸法を選ぶ関数（Python の `dimensioning.chains`）を core に移し、
   組み立てられる全件について Python の結果と比べる。紙面の組み方は決定 3 で変えたので比べない。

## 紙面

- 用紙は A4・A3・A2・A1 の横向き（297×210、420×297、594×420、841×594mm）。既定は A3、大文字と小文字は区別しない。
- 枠は余白 10mm（A4・A3）または 20mm（A2・A1）の内側（A3 なら 400×277mm）。
- 表題欄は枠の右下。部品図の題名と同じ書き方（属性の名前は太字、値の始まりをそろえる。外側だけ線で囲み、行の間に線は引かない）で、次の行を並べる。
  字の大きさは寸法の数字と同じ（数字の高さ 2.5mm）。大きさは中身に合わせる。

  ```
  Title:        file-wagon
  Scale:        1:5.5
  Units:        mm
  Date:         2026-11-02
  Drawing No.:  ND-1
  Designed by:  nichiyou-daiku
  ```

- 図の置き方は Python 版（`shell/drawing.py: _layout`）のまま、枠と表題欄だけ新しい大きさにする。
  - 平面図（from +z）を左上、正面図（from +y）をその下、右側面図（from -x）を正面図の右に置き、3 つは同じ縮尺。図どうしの
    間は 12mm、枠から図までは 4mm。寸法を入れるときは、寸法の段の分を左と下に空ける。
  - 縮尺は枠に入るいちばん大きいもの。1:1 まで、分母は 0.1 刻みに切り上げる（書いた縮尺と描いた縮尺が一致する）。
  - 立体図（from -x +y +z）は、右側面図の右・表題欄の上の空きの 9 割に入る大きさで、その中央に置く（縮尺は書かない）。
  - 正投影の 3 図は見える線と隠れ線（点線）、立体図は見える線だけ。穴も描く。箱どうしの隠れ線（`hidden.rs`）を使う。
- 寸法（Python 版と同じ 5 本の直列寸法）: 正面図の高さ（すべての部材で区切る）と幅、右側面図の奥行き（どちらも立っている部材で
  区切る）、平面図の幅と奥行き（いちばん上の層の部材で区切る）。描き方は部品図・手順の図の寸法（`chain.rs`）と同じ。
  - 部材がつながっていない設計には寸法を入れない。`--no-dimensions` でも入れない。
  - 入りきらない数値は、Python 版と同じ文で知らせる（`… do not fit beside their chain without crossing its lines.` に続けて、
    A1 以外は `Use a larger page (drawing --page-size A2) or leave the dimensions out (drawing --no-dimensions)`、A1 は
    `Leave the dimensions out (drawing --no-dimensions)`）。
- 描き方のクレートに `technical.rs` を置き、紙面の SVG（mm）と、知らせる文を返す。resvg と svg2pdf には頼らない（後で
  ビューアーにも出せる）。

## CLI

- `drawing FILE [-o PATH] [--title T] [--drawing-number N] [--designed-by NAME] [--page-size A4|A3|A2|A1]
  [--no-dimensions] [--fillet-radius R]`。既定は Python 版と同じ（`ND-1`、`nichiyou-daiku`、`A3`）。
- 既定の出力は `<入力>.pdf`。拡張子が `.svg`（大文字小文字を問わない）なら SVG を書く。標準入力 `-` のときは `-o` が要り、
  入力のファイルは上書きしない。題名の既定は入力のファイル名（拡張子なし）、標準入力なら出力のファイル名（拡張子なし）。
- `--fillet-radius` は受け付けるが使わない（角を丸めずに描く。render・steps と同じ）。
- メッセージ（Python 版と同じ文）:
  - 組み立ての問題は `Warning: …`。
  - つながっていない設計で寸法を入れるとき: `Warning: the drawing has no dimensions: the pieces are in N separate parts.
    Connect them to dimension it`。
  - 入りきらない数値: `Warning: …`。
  - 成功: `Successfully created technical drawing: PATH`。
  - 書けないとき: `Error converting to PDF: cannot write PATH: …`（SVG なら `Error exporting SVG: cannot write PATH: …`）。
    R4b1 と同じくファイルの場所を出す。
- 日付は今日（手元の時刻、`YYYY-MM-DD`）。

## PDF

- CLI のクレートの `pdf.rs`: SVG を usvg 0.45 で読み、svg2pdf 0.13（`default-features = false, features = ["text"]`）で
  PDF にする。紙の大きさは SVG の mm のまま（A3 は 1190.55×841.89pt）。
- 字体の読み込みは `png.rs` から `fonts.rs` に移し、PNG と PDF で共有する。
- resvg は 0.45（`default-features = false, features = ["text"]`）に下げる。

## テスト

- core の図面の直列寸法: `tools/make_goldens.py --steps-only` で組み立てられる 671 件の Python の `chains` を `NAME.chains.json`
  （図・軸・側・区切り・区間）に書き、全件で比べる。
- 描き方のクレート: 用紙ごとの枠と表題欄、縮尺（1:1 以下、分母は 0.1 刻みに切り上げ）、正投影の 3 図が枠の中で表題欄と
  重ならないこと、立体図が自分の場所に収まること、隠れ線が正投影の 3 図にだけあること、表題欄の行、つながっていない設計と
  寸法なしで寸法が無いこと、入りきらない数値の知らせの文（A1 では大きい紙を勧めない）。
- CLI: PDF が `%PDF-` で始まり MediaBox が用紙どおり、`.svg` で SVG、標準入力の `-o`、入力を上書きしない、つながっていない
  設計の警告、成功のメッセージ、書けないときにファイルの場所を出す。
- resvg を下げても R4b1 の PNG のテストと CLI の画像のテストが通る。
- 見た目: ファイルワゴンの図面（Rust 版の PDF）をユーザーが Python 版と見比べて確かめる。

## R4b2 で作らないもの

ビューアーに図面を出すこと、`view`（R4c）、角を丸めた描き方、複数の紙に分けること。

## R4b2 が終わる条件

- 上のテストがすべて通り、`make check` と `make ci-local` が通る。
- ユーザーが図面を見て確かめた。
