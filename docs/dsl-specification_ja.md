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

## 基本構造

`.nd`ファイルは以下の要素で構成されます：

1. **コメント** - `//` で始まる行
2. **ピース定義** - 木材の定義
3. **接続定義** - ピース間の接続

```nd
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

```
(piece_id:piece_type =length)
(piece_id:piece_type {"length": length})
```

### パラメータ

| パラメータ | 説明 | 必須 |
|-----------|------|------|
| `piece_id` | ピースの一意な識別子 | はい |
| `piece_type` | 木材の種類 (`1x4`, `2x4`) | はい |
| `length` | 長さ (mm) | はい |

### 木材タイプ

| タイプ | 幅 (mm) | 高さ (mm) | 説明 |
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

### 接続モデル

nichiyou-daikuでは、**2つのピースは必ず辺を共有して接続します**。これは実際の木工接合をモデル化した基本的な制約です。

#### 接続の仕組み

各ピースは6つの面（top, down, left, right, front, back）と12本の辺を持つ直方体です。2つのピースが接続するとき：

1. **接触面 (Contact Face)**: 相手のピースに触れる面
2. **エッジ共有面 (Edge Shared Face)**: 接続点で共有される辺を持つ面
3. **オフセット (Offset)**: 共有辺に沿った位置

```
         ┌─────────────────┐
         │                 │
         │   ベースピース   │
         │                 │
         └────────┬────────┘
                  │ ← 接触面同士がここで接する
         ┌────────┴────────┐
         │                 │
         │  ターゲットピース │
         │                 │
         └─────────────────┘
```

#### 辺共有の制約

両ピースの接触面は共通の辺を共有する必要があります。つまり：

- **contact_face** は相手のピースに触れる面を決定
- **edge_shared_face** は接触面のどの辺で揃えるかを決定
- 2つのピースは contact_face ∩ edge_shared_face で形成される辺で接する

```
例: T字接合

       edge_shared_face = "front"
              ↓
    ┌─────────┼─────────┐
    │         │         │
    │   contact_face    │  ← ベース（水平）
    │      = "top"      │
    └─────────┴─────────┘
              │
    ┌─────────┴─────────┐
    │   contact_face    │
    │     = "down"      │  ← ターゲット（垂直）
    │         │         │
    │ edge_shared_face  │
    │    = "front"      │
    └─────────┴─────────┘
```

#### アンカーの構成要素

**アンカー**は、ピース上の接続点を定義します：

| 構成要素 | 説明 |
|----------|------|
| `contact_face` | 相手のピースに触れる面 |
| `edge_shared_face` | contact_faceと共有する辺を持つ面 |
| `offset` | 共有辺に沿った距離 |

**有効な面の組み合わせ**: contact_faceとedge_shared_faceは隣接している必要があります（対向面は不可）。例：
- ✓ `top` + `front`（隣接面）
- ✓ `left` + `back`（隣接面）
- ✗ `top` + `down`（対向面 - 無効）
- ✗ `left` + `right`（対向面 - 無効）

### 構文

```
base_piece -[base_anchor target_anchor connection_type?]- target_piece
```

### アンカー表記

アンカーは、ピースのどの面でどの位置に接続するかを指定します。

#### 簡略表記（推奨）

```
XY<offset  または  XY>offset
```

- **X**: 接触面 (contact_face)
- **Y**: エッジ共有面 (edge_shared_face)
- **<offset**: FromMin (最小位置からのオフセット)
- **>offset**: FromMax (最大位置からのオフセット)

#### 面の略記

| 略記 | 面 | 説明 |
|------|-----|------|
| `T` | top | 上面 |
| `D` | down | 下面 |
| `L` | left | 左面 |
| `R` | right | 右面 |
| `F` | front | 前面 |
| `B` | back | 後面 |

#### オフセット

| 表記 | 意味 | 説明 |
|------|------|------|
| `<0` | FromMin(0) | 最小位置から0mm |
| `<100` | FromMin(100) | 最小位置から100mm |
| `>0` | FromMax(0) | 最大位置から0mm |
| `>50` | FromMax(50) | 最大位置から50mm |

### 例

```nd
// leg_1の左面・後面エッジ、最大位置から0mmの位置に
// apron_frontの下面・後面エッジ、最大位置から0mmの位置を接続
leg_1 -[LB>0 DB>0]- apron_front

// leg_1の後面・右面エッジ、最小位置から100mmの位置に
// apron_leftの下面・後面エッジ、最小位置から0mmの位置を接続
leg_1 -[BR<100 DB<0]- apron_left
```

### JSON形式（高度な用途）

```nd
piece1 -[{"contact_face": "top", "edge_shared_face": "front", "offset": FromMin(0)}
         {"contact_face": "down", "edge_shared_face": "left", "offset": FromMax(100)}]- piece2
```

## 接続タイプ

接続の種類を指定できます。省略時は `V` (vanilla) になります。

### Vanilla接続 (V)

デフォルトの接続。特別な補強なし。

```nd
piece1 -[TF<0 BD<0]- piece2        // 暗黙的にVanilla
piece1 -[TF<0 BD<0 V]- piece2      // 明示的にVanilla
```

### ダボ接続 (D)

ダボ（木ダボ）を使用した接続。

#### 数値指定

```nd
piece1 -[TF<0 BD<0 D(radius, depth)]- piece2
```

- `radius`: ダボの半径 (mm)
- `depth`: ダボの深さ (mm)

#### プリセット指定

```nd
piece1 -[TF<0 BD<0 D(:diameter x length)]- piece2
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

#### 例

```nd
// 数値指定: 半径4mm、深さ20mmのダボ
piece1 -[TF<0 BD<0 D(4.0, 20.0)]- piece2

// プリセット: 直径8mm、長さ30mmのダボ
piece1 -[TF<0 BD<0 D(:8x30)]- piece2
```

### スクリュー接続 (S)

ねじを使用した接続。

#### 数値指定

```nd
piece1 -[TF<0 BD<0 S(diameter, length)]- piece2
```

- `diameter`: ねじの直径 (mm)
- `length`: ねじの長さ (mm)

#### プリセット指定

```nd
piece1 -[TF<0 BD<0 S(Type:diameter x length)]- piece2
```

**Slim (スリムねじ)**

| プリセット | 直径 (mm) | 長さ (mm) |
|------------|-----------|-----------|
| `Slim:3.3x30` | 3.3 | 30 |
| `Slim:3.3x40` | 3.3 | 40 |
| `Slim:3.3x50` | 3.3 | 50 |
| `Slim:3.3x65` | 3.3 | 65 |
| `Slim:3.8x30` | 3.8 | 30 |
| `Slim:3.8x40` | 3.8 | 40 |
| `Slim:3.8x50` | 3.8 | 50 |
| `Slim:3.8x65` | 3.8 | 65 |
| `Slim:4.2x50` | 4.2 | 50 |
| `Slim:4.2x65` | 4.2 | 65 |
| `Slim:4.2x75` | 4.2 | 75 |

**Coarse (コーススレッドねじ)**

| プリセット | 直径 (mm) | 長さ (mm) |
|------------|-----------|-----------|
| `Coarse:3.8x32` | 3.8 | 32 |
| `Coarse:3.8x38` | 3.8 | 38 |
| `Coarse:3.8x45` | 3.8 | 45 |
| `Coarse:3.8x51` | 3.8 | 51 |
| `Coarse:3.8x57` | 3.8 | 57 |
| `Coarse:3.8x65` | 3.8 | 65 |
| `Coarse:3.8x75` | 3.8 | 75 |
| `Coarse:3.8x90` | 3.8 | 90 |
| `Coarse:4.2x65` | 4.2 | 65 |
| `Coarse:4.2x75` | 4.2 | 75 |
| `Coarse:4.2x90` | 4.2 | 90 |

#### 例

```nd
// 数値指定: 直径3.5mm、長さ50mmのねじ
piece1 -[BF<0 FB<0 S(3.5, 50)]- piece2

// プリセット: スリムねじ 3.3x50
piece1 -[BF<0 FB<0 S(Slim:3.3x50)]- piece2

// プリセット: コーススレッド 3.8x57
piece1 -[BF<0 FB<0 S(Coarse:3.8x57)]- piece2
```

## 完全な例

### コーナー接合

```nd
// コーナー接合サンプル
(corner_piece_a:2x4 =400)
(corner_piece_b:2x4 =400)

corner_piece_a -[TF<0 BD<0]- corner_piece_b
```

### シンプルテーブル

```nd
// Simple Table Design
// 4本脚のテーブル

// 脚
(leg_1:2x4 =720)
(leg_2:2x4 =720)
(leg_3:2x4 =720)
(leg_4:2x4 =720)

// 幕板
(apron_front:2x4 =622)
(apron_back:2x4 =622)
(apron_left:2x4 =524)
(apron_right:2x4 =524)

// 天板
(table_top_1:2x4 =600)
(table_top_2:2x4 =600)

// 脚と幕板の接続
leg_1 -[LB>0 DB>0]- apron_front
leg_2 -[RF>0 TF>0]- apron_front
leg_3 -[LB>0 DB>0]- apron_back
leg_4 -[RF>0 TF>0]- apron_back

// サイド幕板の接続
leg_1 -[BR<100 DB<0]- apron_left
leg_3 -[FR<100 TB<0]- apron_left

// 天板の接続
table_top_1 -[BD<0 TF<0]- leg_1
table_top_2 -[BD<0 TF<0]- leg_2
```

### ダボ接続を使用した棚

```nd
// 棚（ダボ接続）
(left_side:2x4 =800)
(right_side:2x4 =800)
(shelf:2x4 =600)

// ダボプリセットを使用
left_side -[RT>100 FT<50 D(:8x30)]- shelf
right_side -[LT>100 FT<50 D(:8x30)]- shelf
```

## CLIツール

### 構文検証

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

COMMENT         = "//" [^\n]*
```

## エラーメッセージ

### 構文エラー

```
DSLSyntaxError: Unexpected token at line 5, column 10
```

### 意味エラー

```
DSLSemanticError: Unknown piece reference: unknown_piece
DSLSemanticError: Duplicate piece ID: leg_1
```

### 検証エラー

```
DSLValidationError: Invalid piece type: 3x4
DSLValidationError: Unknown dowel preset: 9x99
DSLValidationError: Unknown Slim screw preset: 3.0x100
```
