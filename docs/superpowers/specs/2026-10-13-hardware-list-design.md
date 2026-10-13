# 金物リスト（Hardware List）設計

- 日付: 2026-10-13
- ステータス: 設計済み
- 対象: M4-1（製作支援: 買うものとしての金物とドリル）
- 進め方: 既存の report への追加なので、計画書は書かずにこの記録から TDD で実装する

## 背景

report の買い物リストには木材しかない。ダボ・ビスは部材ごとの下穴の一覧（Pilot Holes）から数えるしかなく、ビスの種類
（スリムビス／コーススレッド）は DSL を読んだ時点で消えている（`S(Slim:3.3x45)` が径と長さだけの `ScrewConnection` になる）。

## 目的

report を読んだ人が、木材と同じく金物とドリルも一度に買い揃えられる。設計スキルの最後の報告にも載る。

## 合意した方針（決定事項と理由）

1. **金物はダボ・ビスの本数を種類と大きさごとに数える。下穴のドリル径も出す**（ユーザーの選択）。予備の本数は出さない
   （店の入り数がまちまちで、固定の割合に意味が薄い）。
2. **ビスの種類をモデルに残す。** `ScrewConnection` に `screw_type`（`slim` / `coarse` / なし）を足す。売り場で別の品物
   なので、径と長さだけでは買えない。数値で書いた `S(3.5, 40)` は種類が分からないので「なし」。
3. **数えるのは実際に置かれた留め具（`assembly.fasteners`）。** 配置と矛盾した接続には留め具が置かれないので、自然に
   数から外れる。`Fastener` 自体は変えず、接続の種類から大きさを引く。

## 設計

- **core:** `ScrewConnection.screw_type: Literal["slim", "coarse"] | None = None`。DSL のプリセット（`Slim:` / `Coarse:`）で入る。
- **shell/resources:** `ResourceSummary` に足す。
  - `hardware`: `HardwareItem`（`name`、`count`）の並び。名前はダボが `Dowel <径>x<全長>`（プリセットと同じ書き方。
    `D(4, 40)` も `Dowel 8x40`）、ビスが `Slim screw <径>x<長さ>`・`Coarse screw ...`・種類なしは `Screw ...`。
    並びはダボ → ビス、その中は径 → 長さ（ビスは種類 → 径 → 長さ）。
  - `drill_bits`: `DrillBit`（`diameter`、`holes`、`deepest`）の並び。下穴（`pilot_holes`）を径ごとにまとめ、穴の数と
    いちばん深い穴の深さ。貫通する穴があれば `deepest` は None（「through」と出す）。径の順。
- **report:** 買い物リストの木材の後に `### Hardware Required:` と `### Drill Bits:`。留め具がなければ出さない。
  - `- **Dowel 8x30**: 32`
  - `- **8mm**: 64 holes, deepest 15mm`（貫通があれば `deepest: through`）
- **スキル:** 手順 8（報告）で、木材に加えて金物とドリルも伝える。
- **ドキュメント:** DSL 仕様の report の説明、API 仕様の `ResourceSummary` と `ScrewConnection`。

## テスト

- DSL: `S(Slim:3.3x45)`・`S(Coarse:3.8x57)`・`S(3.5, 40)` の `screw_type`。
- resources: ダボとビスを混ぜたモデルの本数・名前・並び、ドリル径ごとの穴の数と深さ（ビスの通し穴は through）、
  矛盾した接続が数に入らないこと。
- report: 2 つの節と行、留め具がないモデルでは節が出ないこと。
- 既存の `ScrewConnection` を比べるテストは新しい欄に合わせる。

## 完了条件

- `make check` が通る。最終レビュー（Opus）の指摘を直す。`make ci-local` が通る。
