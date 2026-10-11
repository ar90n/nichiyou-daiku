# nichiyou-daiku DSL Specification

nichiyou-daiku DSL (`.nd`ファイル) は、木工家具の設計を簡潔に記述するためのドメイン固有言語です。Cypherライクな構文で、木材ピースとその接続を定義します。

## 目次

- [基本構造](#基本構造)
- [コメント](#コメント)
- [ピース定義](#ピース定義)
- [接続定義](#接続定義)
- [接続タイプ](#接続タイプ)
- [完全な例](#完全な例)
- [CLIツール](#cliツール)
- [文法 (EBNF)](#文法-ebnf)

## 基本構造

`.nd`ファイルは以下の要素で構成されます：

1. **コメント** - `//` で始まる行
2. **ピース定義** - 木材の定義
3. **接続定義** - ピース間の接続（参照するピースは接続より前に定義しておく必要があります）

```text
// コメント
(piece_id:piece_type =length)
piece1 -[anchor1 anchor2]- piece2
```

## コメント

単一行コメントは `//` で開始します。行末コメントも可能です。

```nd
// これはコメントです
(leg:2x4 =720)  // 行末コメント

// 複数行のコメント
// プロジェクト: ダイニングテーブル
// 作成日: 2025-07-30
```

## ピース定義

木材ピースを定義します。

### 構文

```text
(piece_id:piece_type =length)
(piece_id:piece_type {"length": length})
```

### パラメータ

| パラメータ | 説明 | 必須 |
|-----------|------|------|
| `piece_id` | ピースの一意な識別子（英字・数字・アンダースコア。数字で始めることはできない） | はい（省略するとUUIDが生成され、接続からは参照できない） |
| `piece_type` | 木材の種類 (`1x4`, `2x4`) | はい |
| `length` | 長さ (mm)。0より大きい値 | はい |

### 木材タイプ

| タイプ | 幅 (mm) | 厚み (mm) | 説明 |
|--------|---------|-----------|------|
| `1x4` | 89 | 19 | 1x4材 (ワンバイフォー) |
| `2x4` | 89 | 38 | 2x4材 (ツーバイフォー) |

### 例

```nd
// 簡略表記（推奨）
(leg_1:2x4 =720)
(shelf:1x4 =600)

// JSON形式（将来の拡張用）
(leg_2:2x4 {"length": 720})
```

## 接続定義

2つのピース間の接続を定義します。

### ピースの座標系と面

各ピースは、それぞれ固有のローカル座標系を持つ直方体です：

- **X** = 幅 (89mm)
- **Y** = 厚み (2x4は38mm、1x4は19mm)
- **Z** = 長さ

```
断面図（top端 = +Z を手前に向けて見た場合）:

                 front (+Y)
            ┌──────────────────┐
  left (-X) │                  │ right (+X)     厚み: 38 (2x4) / 19 (1x4)
            └──────────────────┘
                 back (-Y)
            ←─────── 89 ───────→

top (+Z) / down (-Z): 両端の木口面（89 x 厚み）。長さはZ方向
front / back: 広い面（89 x 長さ）
left / right: 細い面（厚み x 長さ）
```

| 面 | 法線 | 種類 | 2x4でのサイズ |
|----|------|------|---------------|
| `top` | +Z | 長さ方向の最大側の木口面 | 89 x 38 |
| `down` | -Z | 長さ方向の最小側の木口面 | 89 x 38 |
| `front` | +Y | 広い面 | 89 x 長さ |
| `back` | -Y | 広い面 | 89 x 長さ |
| `right` | +X | 細い面 | 38 x 長さ |
| `left` | -X | 細い面 | 38 x 長さ |

面の名前は各ピースのローカルな名前です。ピースを水平に置いた場合でも、`top`/`down` は常にピースの両端（木口）を指します。

### 接続モデル

nichiyou-daikuでは、**2つのピースは必ず辺を共有して接続します**。これは実際の木工接合をモデル化した基本的な制約です。

#### アンカーの構成要素

各接続は、ピースごとに1つずつ、合計2つの**アンカー**を持ちます：

| 構成要素 | 説明 |
|----------|------|
| `contact_face` | 相手のピースに触れる面 |
| `edge_shared_face` | contact_faceに隣接する面。アンカーは2つの面が交わる辺の上にある |
| `offset` | その辺に沿ったアンカー点の位置 |

**有効な面の組み合わせ**: contact_faceとedge_shared_faceは隣接している必要があります（同じ面・対向面は不可）。例：
- ✓ `top` + `front`（隣接面）
- ✓ `left` + `back`（隣接面）
- ✗ `top` + `down`（対向面 - 無効）
- ✗ `left` + `right`（対向面 - 無効）
- ✗ `front` + `back`（対向面 - 無効）

#### 辺の向きとオフセット

辺は2つの面の両方に垂直な軸に沿って伸びます。これによりオフセットが何を測るかが決まります：

| 面の組み合わせ（順不同） | 辺の方向 | 辺の長さ (2x4 / 1x4) | FromMin (`<v`) の基準 | FromMax (`>v`) の基準 |
|--------------------------|----------|----------------------|-----------------------|-----------------------|
| top/down + front/back | 幅方向 (X) | 89 / 89 | left側 | right側 |
| top/down + left/right | 厚み方向 (Y) | 38 / 19 | back側 | front側 |
| front/back + left/right | 長さ方向 (Z) | L / L | down端 | top端 |

オフセットは辺の長さを超えられません。例えば2x4で `TL<50` はエラーです（top/leftの辺は38mmしかありません）。

#### 配置ルール

`base -[base_anchor target_anchor]- target` では、ターゲットは次のように配置されます：

1. **接触**: 2つのcontact_faceが面同士で接する。
2. **面一**: 2つのedge_shared_faceが同じ平面上にあり、同じ向きを向く。
3. **点の一致**: 2つのアンカー点が一致する。ターゲット側が `<` ならターゲットの最小側の端（down/left/back）が、`>` なら最大側の端（top/right/front）がその点に来る。

#### 具体例

床（z=0）に立てた2x4の脚（L=700）と、2x4の幕板（L=500）：

```nd
(leg:2x4 =700)
(apron:2x4 =500)
leg -[FL<100 DF<0]- apron
```

- `FL<100`（脚）: 脚のfront面が接触面。front/leftの辺は脚の長さ方向に伸び、点は脚のdown端から100mm上。
- `DF<0`（幕板）: 幕板のdown端が脚のfront面に接するので、幕板は脚からまっすぐ外へ伸びる。幕板のfront面は脚のleft面と面一。幕板のleft側が点に来るので、幅89mmは点から下に垂れ、幕板は z=11..100 を占める。
- `DF>0` にすると幕板のright側が点に来る: z=100..189。
- `FL>100` にすると点は脚のtopから100mm下（z=600）: z=511..600。
- `leg -[RF<100 LF<0]- apron` では、幕板は脚のright面に沿って立ち（front面同士が面一）、z=100 から z=600 まで伸びる。

### 構文

```text
base_piece -[base_anchor target_anchor connection_type?]- target_piece
```

同じbase/targetの組に対する接続は1つだけです。ピースを自分自身に接続することはできません。

### アンカー表記

アンカーは、ピースのどの面でどの位置に接続するかを指定します。

#### 簡略表記（推奨）

```text
XY<offset  または  XY>offset
```

- **X**: 接触面 (contact_face)
- **Y**: エッジ共有面 (edge_shared_face)
- **<offset**: FromMin (辺の最小側の端からのオフセット)
- **>offset**: FromMax (辺の最大側の端からのオフセット)

#### 面の略記

| 略記 | 面 | 説明 |
|------|-----|------|
| `T` | top | 長さ方向の最大側の木口面 (+Z) |
| `D` | down | 長さ方向の最小側の木口面 (-Z) |
| `L` | left | 細い面 (-X) |
| `R` | right | 細い面 (+X) |
| `F` | front | 広い面 (+Y) |
| `B` | back | 広い面 (-Y) |

`B` は **back（後面）** であり、底（bottom）ではありません。ピースの下端は `D`（down）なので、「front面 + 下端」は `FD` または `DF` と書きます。`FB`/`BF` は無効です。

#### オフセット

| 表記 | 意味 | 説明 |
|------|------|------|
| `<0` | FromMin(0) | 辺の最小側の端（down端 / left側 / back側） |
| `<100` | FromMin(100) | 最小側の端から100mm |
| `>0` | FromMax(0) | 辺の最大側の端（top端 / right側 / front側） |
| `>50` | FromMax(50) | 最大側の端から50mm |

### 例

```nd
(leg_1:2x4 =720)
(apron_front:2x4 =600)
(apron_left:2x4 =400)

// leg_1のleft面、left/back辺の脚のtop位置（>0）に、
// apron_frontのdown端、down/back辺のright側（>0）を接続:
// apron_frontはleg_1のleft面から伸び、脚のtopと面一になる
leg_1 -[LB>0 DB>0]- apron_front

// leg_1のback面、back/right辺のdown端から100mmの位置に、
// apron_leftのdown端、down/back辺のleft側（<0）を接続
leg_1 -[BR<100 DB<0]- apron_left
```

### JSON形式（高度な用途）

```nd
(leg:2x4 =700)
(apron:2x4 =500)
leg -[{"contact_face": "front", "edge_shared_face": "left", "offset": FromMin(100)}
      {"contact_face": "down", "edge_shared_face": "front", "offset": FromMin(0)}]- apron
```

## 接続タイプ

接続の種類を指定できます。省略時は `V` (vanilla) になります。

### Vanilla接続 (V)

デフォルトの接続。特別な補強も穴もありません。

```nd
(a:2x4 =400)
(b:2x4 =400)
(c:2x4 =400)
a -[TF<0 BD<0]- b        // 暗黙的にVanilla
a -[FL<200 DF<0 V]- c    // 明示的にVanilla
```

### ダボ接続 (D)

ダボ（木ダボ）を使用した接続。

#### 数値指定

```text
piece1 -[anchor anchor D(radius, length)]- piece2
```

- `radius`: ダボの半径 (mm)
- `length`: ダボの**全長** (mm)。半分ずつ各ピースに入る

#### プリセット指定

```text
piece1 -[anchor anchor D(:直径x長さ)]- piece2
```

利用可能なプリセット:

| プリセット | 直径 (mm) | 長さ (mm) |
|------------|-----------|-----------|
| `6x25` | 6 | 25 |
| `6x30` | 6 | 30 |
| `8x25` | 8 | 25 |
| `8x30` | 8 | 30 |
| `8x40` | 8 | 40 |
| `10x30` | 10 | 30 |
| `10x40` | 10 | 40 |
| `12x40` | 12 | 40 |

#### ルール

- ダボの長さの半分は、各ピースの接触面の法線方向の寸法より短くなければなりません。同じだと穴が裏まで抜けるためです（front/back接触 → 厚み（38または19）、left/right → 89、top/down → ピースの長さ）。
- 穴: 各ピースに 直径 x 長さ/2 の穴があきます。
- ダボとビス: 接触面の短辺は留め具の直径の 2 倍以上必要です（辺でしか接していない部材には接触面がありません）。満たさない場合は `validate` が報告し、穴はあきません。2 つの接続の穴が部材の中でぶつかる場合も報告します。

#### 例

```nd
(a:2x4 =400)
(b:2x4 =400)
(c:2x4 =400)

// プリセット: 直径8mm、全長30mmのダボ
a -[TF<0 BD<0 D(:8x30)]- b

// 数値指定: 半径4mm、全長30mmのダボ（各ピースに15mmずつ）
a -[FL<200 DF<0 D(4, 30)]- c
```

### ビス接続 (S)

ビス（ねじ）を使用した接続。ビスはターゲットを貫通してベースに打ち込まれます。

#### 数値指定

```text
piece1 -[anchor anchor S(diameter, length)]- piece2
```

- `diameter`: ビスの直径 (mm)
- `length`: ビスの長さ (mm)

#### プリセット指定

```text
piece1 -[anchor anchor S(種類:直径x長さ)]- piece2
```

**Slim (スリムビス)**

| プリセット | 直径 (mm) | 長さ (mm) |
|------------|-----------|-----------|
| `Slim:3.3x25` | 3.3 | 25 |
| `Slim:3.3x30` | 3.3 | 30 |
| `Slim:3.3x35` | 3.3 | 35 |
| `Slim:3.3x40` | 3.3 | 40 |
| `Slim:3.3x45` | 3.3 | 45 |
| `Slim:3.3x50` | 3.3 | 50 |
| `Slim:3.8x55` | 3.8 | 55 |
| `Slim:3.8x60` | 3.8 | 60 |
| `Slim:3.8x65` | 3.8 | 65 |
| `Slim:3.8x70` | 3.8 | 70 |
| `Slim:3.8x75` | 3.8 | 75 |
| `Slim:4.2x90` | 4.2 | 90 |

**Coarse (コーススレッド)**

| プリセット | 直径 (mm) | 長さ (mm) |
|------------|-----------|-----------|
| `Coarse:3.8x25` | 3.8 | 25 |
| `Coarse:3.8x30` | 3.8 | 30 |
| `Coarse:3.8x35` | 3.8 | 35 |
| `Coarse:3.8x40` | 3.8 | 40 |
| `Coarse:3.8x45` | 3.8 | 45 |
| `Coarse:3.8x50` | 3.8 | 50 |
| `Coarse:3.8x57` | 3.8 | 57 |
| `Coarse:4.2x65` | 4.2 | 65 |
| `Coarse:4.2x75` | 4.2 | 75 |
| `Coarse:4.5x90` | 4.5 | 90 |
| `Coarse:4.5x100` | 4.5 | 100 |
| `Coarse:5.2x120` | 5.2 | 120 |

#### ルール

- ターゲットのcontact_faceは `front` または `back` でなければなりません（ビスはターゲットの広い面を貫通します）。
- ビスの長さはターゲットの厚み（2x4は38、1x4は19）より長くなければなりません。
- ビスの長さは「ベースの接触面の法線方向の寸法（front/back → 厚み、left/right → 89、top/down → ピースの長さ）+ ターゲットの厚み」より短くなければなりません。先端がベースの裏に出ないようにするためです。
- 穴: ターゲットには貫通穴、ベースには (長さ - ターゲットの厚み) の深さの穴があきます。

#### 例

```nd
(post:2x4 =600)
(rail:2x4 =400)
(rail_low:2x4 =400)
(cleat:2x4 =400)

// プリセット: スリムビス 3.3x50。railを柱のfront面に横向きにビス留め
post -[FL<300 BT<0 S(Slim:3.3x50)]- rail

// 数値指定: 直径3.5mm、長さ50mmのビス
post -[FL<100 BT<0 S(3.5, 50)]- rail_low

// プリセット: コーススレッド 3.8x57。cleatを柱の裏に面同士でビス留め
post -[BT<0 FT<0 S(Coarse:3.8x57)]- cleat
```

## 完全な例

### コーナー接合

```nd
// コーナー接合サンプル: corner_piece_bがcorner_piece_aのtop端の上に横たわる
(corner_piece_a:2x4 =400)
(corner_piece_b:2x4 =400)

corner_piece_a -[TF<0 BD<0]- corner_piece_b
```

### シンプルテーブル

脚は正面に89mmの面、側面に38mmの面を向けます。幕板はすべて高さ89mmで脚の間に入り、脚のtopと面一です。そのため前後の幕板の長さは W - 2x89、左右の幕板は D - 2x38 になります。

```nd
// シンプルテーブル: 800 (W) x 600 (D) x 758 (H)

// 脚: leg_1 左前, leg_2 右前, leg_3 左奥, leg_4 右奥
(leg_1:2x4 =720)
(leg_2:2x4 =720)
(leg_3:2x4 =720)
(leg_4:2x4 =720)

// 幕板: 800 - 2x89 = 622, 600 - 2x38 = 524
(apron_front:2x4 =622)
(apron_back:2x4 =622)
(apron_left:2x4 =524)
(apron_right:2x4 =524)

// 天板（2x4、前後方向）
(table_top_1:2x4 =600)
(table_top_2:2x4 =600)

// 脚と前後の幕板の接続
leg_1 -[LB>0 DB>0]- apron_front
leg_2 -[RF>0 TF>0]- apron_front
leg_3 -[LB>0 DB>0]- apron_back
leg_4 -[RF>0 TF>0]- apron_back

// サイド幕板の接続
leg_1 -[BR>0 DB>0]- apron_left
leg_3 -[FR>0 TB>0]- apron_left
leg_2 -[BL>0 DF>0]- apron_right
leg_4 -[FL>0 TF>0]- apron_right

// 天板の接続: 両端の板は脚のtopに載る
table_top_1 -[BD<0 TF<0]- leg_1
table_top_2 -[BD<0 TF<0]- leg_2
```

天板をすべて張った大きな例は [`examples/nd_files/simple_table_compact.nd`](../examples/nd_files/simple_table_compact.nd) を参照してください（そちらではサイド幕板が床から100mmの位置にあります。`BR<100`）。

### ダボ接続を使用した棚

```nd
// 棚（ダボ接続）: 676 (W) x 89 (D) x 800 (H)
(left_side:2x4 =800)
(right_side:2x4 =800)
(shelf:2x4 =600)

// 棚板の両端を側板の広い面に接続。棚板の下面は床から300mm
left_side -[BL<300 DL<0 D(:8x30)]- shelf
right_side -[FL<300 TL<0 D(:8x30)]- shelf
```

## CLIツール

### 検証

ファイルが記述するモデルを検証します。

```bash
nichiyou-daiku validate furniture.nd
```

### レポート生成

```bash
nichiyou-daiku report furniture.nd -o report.md
nichiyou-daiku report furniture.nd --project-name "My Table"
```

### 3Dビュー (build123d必須)

```bash
nichiyou-daiku view furniture.nd
```

### エクスポート (build123d必須)

```bash
# STL形式
nichiyou-daiku export furniture.nd -f stl

# STEP形式
nichiyou-daiku export furniture.nd -f step -o model.step

# フィレット半径指定
nichiyou-daiku export furniture.nd -f stl --fillet-radius 10
```

### 図面 (build123d必須)

```bash
nichiyou-daiku drawing furniture.nd -o furniture.pdf
```

## 文法 (EBNF)

```ebnf
start           = statement+
statement       = piece_def | connection_def

piece_def       = "(" CNAME? ":" PIECE_TYPE (piece_props | compact_length) ")"
PIECE_TYPE      = "1x4" | "2x4"
piece_props     = "{" prop_list? "}"
compact_length  = "=" NUMBER
prop_list       = prop ("," prop)*
prop            = ESCAPED_STRING ":" value

connection_def  = piece_ref "-[" connection_body "]-" piece_ref
connection_body = anchor_props anchor_props connection_type_props?
                | compact_anchor compact_anchor compact_connection_type?
piece_ref       = CNAME

anchor_props         = "{" anchor_prop_list? "}"
anchor_prop_list     = anchor_prop ("," anchor_prop)*
anchor_prop          = ESCAPED_STRING ":" (ESCAPED_STRING | offset_value)
offset_value         = "FromMin" "(" NUMBER ")" | "FromMax" "(" NUMBER ")"

connection_type_props = "{" ( '"type": "vanilla"'
                            | '"type": "dowel", "radius": ' NUMBER ', "depth": ' NUMBER
                            | '"type": "screw", "diameter": ' NUMBER ', "length": ' NUMBER ) "}"

compact_anchor       = COMPACT_FACE COMPACT_FACE compact_offset
compact_offset       = "<" NUMBER | ">" NUMBER
COMPACT_FACE         = "T" | "D" | "L" | "R" | "F" | "B"

compact_connection_type = "V" | dowel_compact | screw_compact
dowel_compact           = "D(" (dowel_preset | dowel_numeric) ")"
dowel_preset            = ":" NUMBER "x" NUMBER
dowel_numeric           = NUMBER "," NUMBER
screw_compact           = "S(" (screw_preset | screw_numeric) ")"
screw_preset            = SCREW_TYPE ":" NUMBER "x" NUMBER
screw_numeric           = NUMBER "," NUMBER
SCREW_TYPE              = "Slim" | "Coarse"

COMMENT         = "//" [^\n]*     (無視される)
```

JSON形式のダボ指定の `depth` は、`D(radius, length)` と同じくダボの全長です。

## エラーメッセージ

エラーには問題のある文の行と列が含まれます。

### 構文エラー

```text
DSLSyntaxError: Syntax error at line 1, column 4: Unexpected token '3'. Expected: piece type (1x4, 2x4)
```

### 意味エラー

```text
DSLSemanticError: Unknown piece reference: unknown_piece
DSLSemanticError: Duplicate piece ID: leg_1
DSLSemanticError: Duplicate connection between 'a' and 'b': only one connection per piece pair is supported
```

### 検証エラー

```text
DSLValidationError: contact_face 'front' and edge_shared_face 'back' must be adjacent faces
DSLValidationError: Offset 50.0mm exceeds piece dimension 38.0mm (piece 'a', edge top/left)
DSLValidationError: Unknown dowel preset: 9x99
DSLValidationError: Unknown Slim screw preset: 3.0x100
DSLValidationError: ScrewConnection target contact_face must be 'front' or 'back', got 'down'
DSLValidationError: Screw length 35.0mm does not reach base piece (target thickness: 38.0mm)
DSLValidationError: Dowel depth 20.0mm (half of 40.0mm) would go through the base piece (19.0mm); use a dowel shorter than 38.0mm
```
