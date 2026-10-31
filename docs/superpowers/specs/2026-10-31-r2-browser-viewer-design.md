# R2 ブラウザのビューアー 設計

- 日付: 2026-10-31
- ステータス: 設計（未実装）
- ブランチ: `next`（作業は `next-r2-viewer`）
- 親: `2026-10-29-next-generation-rust-core-design.md`（次世代の R2）

## 目的

.nd を URL か手元のファイルから開き、3D で回して見て、validate の問題を一覧で確かめられるビューアーを作る。
計算は R1 の Rust の core（WASM）で、全部ブラウザの中で動く。サーバーは静的なファイルを配るだけで、.nd を
どこにも送らない。

## 決定と理由

1. **公開して URL で共有できる形にする**（ユーザー）。GitHub Pages に置き、`?src=<.nd の URL>` で開ける
   （GitHub の raw や gist の URL）。手元の .nd もファイルを選ぶかドラッグして開ける。公開の仕組み（Actions）
   までは作るが、Pages を有効にすることと実際に公開することはユーザーが決めて行う。
2. **最初の版に入れるもの**（ユーザー）: 部材の箱と部材名のラベル、問題の一覧に加えて、
   - 穴と問題の強調（下穴・ダボ穴・座掘りを描き、問題を押すと関わる部材や穴を色で示す）
   - 部材を押すと情報（ID・材種・長さ・何行目か・つながる接続）
   - .nd の本文を横に（行番号つき、エラーの行に印。編集はしない）
   - 視点のボタン（正面・上・右・斜め）
3. **画面は Vite + TypeScript + three.js、計算は Rust の WASM**（ユーザー、2026-10-31）。今の Web の主流に
   乗り、three.js は Web の 3D で一番使われていて情報が多い。全部 Rust（Leptos/Dioxus + three-d、egui）も
   比べたが、three-d は実績と既製の部品（ラベル、輪郭線）が少なく、egui は日本語フォントの同梱が要る。
   three.js は当初私が言い出したもので、ユーザーが選び直した。
4. **WASM の包みは wasm-bindgen、wasm-pack は使わない**。Rust を Web で使うときの標準で、文字列の受け渡しを
   安全に作り、TypeScript の型定義も出す。wasm-pack は 2025 年に rustwasm の組織が閉じたときに手を離れた。
   wasm-bindgen を使うのは包みのクレートだけで、core には入れない（core の依存は serde と serde_json のまま）。
   道具（wasm-bindgen-cli）はライブラリと同じ版に固定する。
5. **core と画面の受け渡しは JSON の文字列 1 つ**（下の「view の JSON」）。`validate --json` と同じ中身に、
   描くための部材の位置と向き、接続、穴、.nd の行番号を足したもの。画面は計算せず、この JSON を描くだけ。
6. **座標はモデルのまま**（z が上、原点はモデルの最小の角、`validate` と同じ）。three.js ではカメラの上を z に
   するだけで、座標を変換しない。視点のボタンは `render` と同じ（正面 +y、上 +z、右 −x、斜め −x +y +z）。
7. **画面の文言は英語**。CLI・エラー・問題の文面と同じ言葉にそろえる（変えたければ後で）。

## 組み立て

- **core（`crates/nichiyou-daiku-core`）**に `view(source: &str) -> serde_json::Value` を足す。.nd の評価で
  部材と接続の位置（行）を返す入口（`dsl` の中）も足す（R1 の評価器はもう位置を持っている）。
- **`crates/nichiyou-daiku-wasm`**（新しい cdylib）: wasm-bindgen で `view(source: &str) -> String` を出す。
  中身は core の `view` を JSON の文字列にするだけ。
- **`web/`**（Vite + TypeScript + three.js、npm）:
  - `load`: `?src=` の URL を取ってくる、ファイルを選ぶ、ドラッグ＆ドロップ。取れないとき（ネットワーク、
    CORS、404）は、何が悪くどう直すか（raw の URL を使う、など）を出す。
  - `model`: WASM を呼んで JSON を型付きのデータにする。
  - `scene`: データから three.js の部品を作る（箱と輪郭線、穴の円柱、ラベルの位置）。WebGL に触れない。
  - `viewer`: 描画、マウスで回す・拡大・移動、視点のボタン、部材を押して選ぶ。
  - `panels`: ヘッダー（ファイル名・外形・問題の件数）、問題の一覧、部材の情報、.nd の本文。
  - `highlight`: 選んだ部材・問題から、色付けする部材と穴と本文の行を決める（WebGL に触れない）。

## view の JSON

`validate --json` と同じキー（`valid`・`error`・`overall_size`・`size_reference`・`pieces`・`problems`）に、
次を足す。`error` があるときは `pieces`・`connections`・`holes` は空。

```json
{
  "pieces": [
    {"id": "leg", "type": "2x4", "length": 500.0, "group": 0,
     "min": [0, 0, 0], "max": [89, 38, 500], "faces": {"top": "+z", "right": "+x", "front": "+y"},
     "size": [89.0, 38.0, 500.0], "position": [0.0, 0.0, 0.0],
     "rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "line": 3}
  ],
  "connections": [
    {"base": "leg", "target": "apron", "kind": "screw", "diameter": 3.8, "length": 65.0,
     "screw_type": "slim", "line": 7}
  ],
  "holes": [
    {"piece": "leg", "kind": "pilot", "center": [44.5, 0.0, 33.0], "direction": "+y",
     "diameter": 2.5, "depth": 27.0}
  ]
}
```

- 部材: `validate` と同じキーに、`size`（幅・厚さ・長さ）、`position` と `rotation`（部材の座標 → 世界:
  `world = rotation · local + position`、原点はモデルの最小の角）、`line`（定義した行）を足す。
- 接続: 書いた順に、`kind`（`vanilla`・`dowel`・`screw`）、大きさ（ダボは `diameter` と `length`、ビスは
  `diameter`・`length`・`screw_type`、ないものは null）、`line`。
- 穴: 部材ごとに、R1 の穴の一覧と同じ穴を世界の座標で。`kind` は `dowel`・`pilot`（ビスの下穴）・
  `counterbore`、`center` は穴が入る面の上の中心、`direction` は穴が進む向き（validate の穴のぶつかりと同じ書き方）、
  `depth` が null なら貫通。

## 画面と動き

```
┌────────────────────────────────────────────────────────────┐
│ [Open] [URL: ________ ] file-wagon.nd   500×440×750mm  ⚠2 │
├──────────────────┬─────────────────────────────────────────┤
│ .nd source       │  [Front][Top][Right][Iso]   [Labels]    │
│  1 // File Wagon │                                         │
│  2 WIDTH = 530   │              3D                         │
├──────────────────┤                                         │
│ Problems (2)     │                                         │
│ Piece            │                                         │
└──────────────────┴─────────────────────────────────────────┘
```

- 開く: `?src=` があれば開いたときに取ってくる。URL の欄で開くとアドレスバーも `?src=` 付きにする（そのまま
  送れる）。ファイルを選ぶかドラッグする（手元のファイルは URL では共有できない）。
- 正しい .nd: 3D に描く。問題があれば ⚠ と件数、一覧に並べる。書き間違い（エラー）: 3D は描かず、エラーの
  文面を一覧の先頭に出し、本文の該当行に印を付けてスクロールする。
- 3D: 部材は木の色の箱に輪郭線。穴は濃い色の円柱（座掘りは太く浅い）。ラベルは部材の中心に HTML で重ね、
  ボタンで切り替える。
- 部材を押す: 色付きにして、情報欄に ID・材種・長さ・行・つながる接続（相手、種類と大きさ）を出す。行や接続を
  押すと本文のその行へ。
- 問題を押す: 矛盾はループの部材、つながっていないはグループごとの色、留め具は 2 つの部材、穴のぶつかりは
  その部材を半透明にして 2 つの穴を赤く、重なりは 2 つの部材を赤く。本文の接続の行へ飛ぶ。
- 本文の行を押す: その行で定義した部材か接続を選ぶ。

## ビルド・公開・テスト

- `make web`: WASM を作り（release、サイズ優先）、wasm-bindgen で包み、Vite で `web/dist` にまとめる。
  `make web-dev` は開発用のサーバー。WASM の大きさは測ってこの文書に書く。
- 公開: `.github/workflows/pages.yml`（手で動かしたときだけ、ビルドして GitHub Pages に置く。公開先は
  `https://ar90n.github.io/nichiyou-daiku/` の見込み）。
- テスト:
  - Rust: 正解ファイルの 769 件すべてで、`view` から足したキーを除くと `validate` と同じになること、
    `position`・`rotation`・`size` から計算した箱が `min`・`max` と一致すること、穴が R1 の穴の一覧
    （部材の座標）を `position`・`rotation` で動かしたものと一致すること。接続の一覧と行番号は単体テスト。
  - TypeScript（vitest、jsdom）: JSON を読む、箱と穴の部品を作る、問題ごとの色付け、`?src=` の扱い、本文の
    行と部材・接続の対応、一覧とエラーの表示。
  - 通し: ビルドした WASM を Node で読み、例の .nd を渡して結果が返ること。
  - 見た目: `make web-dev` でファイルワゴンを開き、ユーザーが見て確かめる。
- `make check` に `web-check`（型検査・vitest・ビルド）を足す。Dagger の CI は、Rust のコンテナで WASM を作り、
  Node のコンテナでテストとビルドをする。

## R2 で作らないもの

編集、CLI からビューアーを開くこと（R3）、図面と組み立て手順（R4）、STL・STEP（R5）、スマートフォン向けの
画面の作り込み。

## R2 が終わる条件

- 上のテストがすべて通り、`make check` と `make ci-local` が通る。
- WASM の大きさを測って書いてある。
- ユーザーが `make web-dev` でファイルワゴンを開き、見た目と動きを確かめた。
