# DSL の変数と式（DSL Variables）設計

- 日付: 2026-10-12
- ステータス: 実装済み（ブランチ feat/dsl-variables）
- 実装との差分: 簡略表記のオフセットは専用の規則（`offset_atom`）にした。共通の `atom` を使うと、LALR の状態が変数定義の直後と共有され、次の面の文字（`DF`）が変数名として読まれるため。`S(` の直後で式を許したので、ビスの種類 `Slim` / `Coarse` の字句に優先度を付けた（`S(...)` の中では変数名に使えない）。
- 対象: M2-4（拡張）の 2 項目目
- 決め方: ユーザーの `/goal`（M2 系の開発を完了させる）により、確認を挟まずに決めた。判断と理由をここに残す。

## 背景

DSL には数値の直書きしかない。寸法から長さやオフセットを計算する家具（例: `examples/long_shelf.py`）は Python で書かれており、
「家具の設計は .nd で書く」という方針と合わない。LLM が .nd を書くときも、手で計算した値（`RF<12.571` など）を埋め込むことになり、
誤りやすい。

## 目的

全体寸法などを変数で置き、長さ・オフセット・留め具の寸法を式で書けるようにする。

## 決定事項と理由

1. **変数は `NAME = 式` の文で定義する。** 定義より後でだけ参照できる（上から順に読めば値が決まる）。再定義はエラー（値が途中で変わると読みにくい）。
2. **式は `+ - * /`・括弧・単項マイナス・数値・変数。** 関数や比較・繰り返しは入れない（今の用途に要らない）。
3. **数値を書ける場所はすべて式を受け付ける。** 長さ（`=式`、JSON の `"length"`）、JSON のオフセット（`FromMin(式)`）、
   ダボ・ビスの数値指定（`D(式, 式)`、`S(式, 式)`、JSON の `radius` など）。
4. **簡略表記のオフセットは「数値・変数・括弧つきの式」に限る。** `FL<W/2` は `FL<(W/2)` と書く。`TF<0 BD<0` のように
   オフセットの直後に次の面の文字が続くので、括弧なしの式を許すと読みにくく、文法も曖昧になりやすい。
5. **プリセット（`D(:8x30)`、`S(Slim:3.3x25)`）は名前なので変えない。**
6. **変数とピース ID は別の名前空間。** 変数は式の中、ピース ID は接続の両端にしか現れないので衝突しない。
7. **エラー:** 未定義の変数（後で定義されるものを含む）と再定義は `DSLSemanticError`、0 での割り算は `DSLValidationError`。
   どれも行と列を付ける。式の結果が不正な値（長さ 0 以下など）になった場合は、今の検証がそのまま報告する。
8. **Python API は変えない。** 変数と式は DSL を読むときに値になり、`Model` には数値だけが残る。

## スコープ外

- 繰り返し・条件・関数（`long_shelf.py` のように部材の数が寸法で変わる設計は、まだ Python で書く）
- 材の寸法を返す組み込み定数（`89` などは数値で書く）
- 長さを接続から決める「未知数」（M2-4 の次の項目）

## 設計

### 文法（`dsl/grammar.py`）

```
statement: piece_def | connection_def | var_def
var_def: CNAME "=" sum

?sum: product | sum "+" product -> add | sum "-" product -> sub
?product: atom | product "*" atom -> mul | product "/" atom -> div
?atom: NUMBER -> number | CNAME -> var | "-" atom -> neg | "(" sum ")"

compact_length: "=" sum
compact_offset: COMPACT_FROM_MIN atom | COMPACT_FROM_MAX atom
offset_value: FROM_MIN "(" sum ")" | FROM_MAX "(" sum ")"
value: ESCAPED_STRING | sum | offset_value
dowel_numeric / screw_numeric / type_dowel / type_screw: 数値の位置を sum に
```

### 変換（`dsl/transformer.py`）

- `DSLTransformer` に `variables: dict[str, float]` を持たせる。Lark の Transformer は文を上から順に処理するので、
  参照時点で定義済みの変数だけが見える。
- `number` / `var` / `neg` / `add` / `sub` / `mul` / `div` のコールバックが float を返す。

## テスト

- 変数の定義と参照、優先順位と括弧、単項マイナス、変数から変数を作る、割り算。
- 長さ・簡略オフセット（数値・変数・括弧）・JSON のオフセットと長さ・ダボとビスの数値指定で式が使える。プリセットは変わらない。
- 面の文字と同じ名前の変数（`T = 50` を `FL<T` で使う）。
- エラー: 未定義、定義より前の参照、再定義、0 除算（行と列つき）、括弧なしの簡略オフセット式は構文エラー。
- 例: `examples/nd_files/simple_table_parametric.nd`（`simple_table_compact.nd` と同じテーブルを全体寸法の変数で書いたもの）が
  `validate` を通り、部材の長さが元の例と一致する。

## ドキュメント

DSL 仕様（英日）に「変数と式」の節と EBNF、`prompts/system.md` の DSL の要約、`prompts/reference/dsl-complete.md` の EBNF、README。
