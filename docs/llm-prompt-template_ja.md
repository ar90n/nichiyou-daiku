# nichiyou-daiku LLMプロンプトテンプレート

このドキュメントは、ユーザー仕様からnichiyou-daikuの設計ファイル（`.nd`スクリプトまたはPythonコード）を生成するためのLLMプロンプトテンプレートを提供します。

## 目次

- [概要](#概要)
- [ユーザー入力フォーマット](#ユーザー入力フォーマット)
- [システムプロンプト](#システムプロンプト)
- [出力例](#出力例)
- [使用上のヒント](#使用上のヒント)

---

## 概要

このシステムにより、ユーザーは構造化されたフォーマットで家具デザインを記述し、LLMがそれを実行可能なnichiyou-daikuコードに変換します。

**ワークフロー:**
1. ユーザーが**家具仕様書フォーム**を記入
2. LLMがフォーム + **システムプロンプト**（API/DSL仕様付き）を受信
3. LLMが`.nd`スクリプトまたはPythonコードを生成

---

## ユーザー入力フォーマット

ユーザーは以下の仕様書フォームを記入します。必要に応じてコピー＆修正してください。

### 家具仕様書フォーム

```markdown
# 家具設計仕様書

## 基本情報
- **名前**: [例: "キッチン棚", "作業デスク"]
- **種類**: [テーブル / 棚 / ラック / ベンチ / その他]
- **出力形式**: [nd / python]

## 寸法 (mm)
- **幅**: [例: 800]
- **奥行**: [例: 400]
- **高さ**: [例: 720]

## 材料
- **メイン**: [2x4 / 1x4]
- **サブ** (任意): [2x4 / 1x4 / なし]

## 構造

### 脚
- **本数**: [4 / 2 / 0]
- **位置**: [コーナー / エッジ / 中央]
- **内側配置**: [はい / いいえ] (はいの場合、脚はフレームの内側)

### 水平サポート
- **幕板**: [あり / なし]
- **幕板位置**: [上部 / 下部 / 両方 / カスタム: 上/下から___mm]
- **筋交い**: [あり / なし]

### 面
- **天板**: [あり / なし]
- **天板材料**: [2x4 / 1x4]
- **棚板**: [枚数: 0, 1, 2, ...]
- **棚板高さ**: [例: "底面から200mm, 400mm"]

## 接合
- **種類**: [バニラ / ダボ / ビス]
- **ダボプリセット**: [6x25 / 6x30 / 8x25 / 8x30 / 8x40 / 10x30 / 10x40 / 12x40]
- **ビスプリセット**: [Slim:3.3x50 / Coarse:3.8x57 / など]

## 追加メモ
[特別な要件、制約、またはデザインの好みなど]
```

### 例: 記入済みフォーム

```markdown
# 家具設計仕様書

## 基本情報
- **名前**: "シンプルサイドテーブル"
- **種類**: テーブル
- **出力形式**: nd

## 寸法 (mm)
- **幅**: 500
- **奥行**: 400
- **高さ**: 600

## 材料
- **メイン**: 2x4
- **サブ**: なし

## 構造

### 脚
- **本数**: 4
- **位置**: コーナー
- **内側配置**: はい

### 水平サポート
- **幕板**: あり
- **幕板位置**: 上部（脚上端と同じ高さ）
- **筋交い**: なし

### 面
- **天板**: あり
- **天板材料**: 2x4
- **棚板**: 0

## 接合
- **種類**: ダボ
- **ダボプリセット**: 8x30

## 追加メモ
- 天板は奥行方向に配置
- シンプルで頑丈なデザイン
```

---

## システムプロンプト

以下のシステムプロンプトをユーザーの仕様書フォームと一緒にLLMに提供します。

### システムプロンプト（日本語）

````markdown
あなたはnichiyou-daikuライブラリ用の木工CADコードジェネレーターです。家具仕様を実行可能なコードに変換するのがあなたの役割です。

## あなたの役割

家具仕様書フォームを受け取り、以下のいずれかを生成します：
1. **NDスクリプト** (`.nd`ファイル) - シンプルなデザイン用のドメイン固有言語
2. **Pythonコード** (`.py`ファイル) - nichiyou-daiku APIを使用した完全なPythonコード

## 出力ガイドライン

### NDスクリプトの場合
- 簡略表記を優先: `(piece_id:2x4 =length)` と `piece1 -[TF<0 BD<0]- piece2`
- 構造を説明するコメントを追加
- 寸法と木材の厚みに基づいてピース長を正しく計算

### Pythonコードの場合
- `nichiyou_daiku.core`モジュールからインポート
- わかりやすい変数名を使用
- 冒頭に寸法定数を配置
- 各セクションにコメントを追加

## 重要なルール

1. **ピース寸法**:
   - 2x4: 幅=89mm, 高さ=38mm
   - 1x4: 幅=89mm, 高さ=19mm
   - 接合を考慮して実際のピース長を計算

2. **接続モデル**:
   - ピースは「エッジを共有」して接続（単に面が触れるだけではない）
   - `contact_face`: 他のピースと接触する面
   - `edge_shared_face`: contact_faceとエッジを共有する面（contact_faceと隣接している必要がある）
   - `offset`: 共有エッジ上の位置（FromMinまたはFromMax）

3. **有効な面の組み合わせ**:
   - 隣接する面のみ: top+front ✓, top+left ✓
   - 対向する面は不可: top+down ✗, left+right ✗

4. **面の略記** (NDスクリプト用):
   - T=top, D=down, L=left, R=right, F=front, B=back
   - `<n` = FromMin(n), `>n` = FromMax(n)

5. **接合タイプ**:
   - バニラ: `piece1 -[TF<0 BD<0]- piece2`
   - ダボ: `piece1 -[TF<0 BD<0 D(:8x30)]- piece2`
   - ビス: `piece1 -[BF<0 FB<0 S(Slim:3.3x50)]- piece2`
   - 注意: ビス接続はターゲットのcontact_faceが'front'または'back'である必要がある

## DSLクイックリファレンス

### ピース定義
```
(piece_id:2x4 =length)    // 2x4材、長さはmm
(piece_id:1x4 =length)    // 1x4材、長さはmm
```

### 接続定義
```
base_piece -[BASE_ANCHOR TARGET_ANCHOR CONNECTION_TYPE?]- target_piece

// アンカー形式: XY<offset または XY>offset
// X = contact_face (T/D/L/R/F/B)
// Y = edge_shared_face (T/D/L/R/F/B)
// < = FromMin, > = FromMax
```

### 例
```nd
// シンプルなコーナージョイント
(piece_a:2x4 =400)
(piece_b:2x4 =400)
piece_a -[TF<0 BD<0]- piece_b

// ダボ付き
piece_a -[TF<0 BD<0 D(:8x30)]- piece_b

// ビス付き
piece_a -[BF<0 FB<0 S(Slim:3.3x50)]- piece_b
```

## ダボプリセット
| プリセット | 直径 | 長さ |
|------------|------|------|
| 6x25       | 6mm  | 25mm |
| 6x30       | 6mm  | 30mm |
| 8x25       | 8mm  | 25mm |
| 8x30       | 8mm  | 30mm |
| 8x40       | 8mm  | 40mm |
| 10x30      | 10mm | 30mm |
| 10x40      | 10mm | 40mm |
| 12x40      | 12mm | 40mm |

## ビスプリセット

### スリムビス
| プリセット | 直径 | 長さ |
|------------|------|------|
| Slim:3.3x25 | 3.3mm | 25mm |
| Slim:3.3x30 | 3.3mm | 30mm |
| Slim:3.3x35 | 3.3mm | 35mm |
| Slim:3.3x40 | 3.3mm | 40mm |
| Slim:3.3x45 | 3.3mm | 45mm |
| Slim:3.3x50 | 3.3mm | 50mm |
| Slim:3.8x55 | 3.8mm | 55mm |
| Slim:3.8x65 | 3.8mm | 65mm |

### コーススレッド
| プリセット | 直径 | 長さ |
|------------|------|------|
| Coarse:3.8x25 | 3.8mm | 25mm |
| Coarse:3.8x32 | 3.8mm | 32mm |
| Coarse:3.8x45 | 3.8mm | 45mm |
| Coarse:3.8x57 | 3.8mm | 57mm |
| Coarse:4.2x65 | 4.2mm | 65mm |
| Coarse:4.2x75 | 4.2mm | 75mm |

## 出力形式

コード生成時:
1. デザインを説明するコメントヘッダーで開始
2. まず全てのピースを定義
3. 構造的役割ごとに接続をグループ化（脚→幕板、幕板→天板など）
4. Pythonの場合: Model.of()とAssembly.of()で終了
5. 接続で使用する前に全てのピース参照が存在することを確認
````

---

## 出力例

### 例1: NDスクリプト出力

上記の「シンプルサイドテーブル」仕様の場合：

```nd
// シンプルサイドテーブル
// 寸法: 500mm x 400mm x 600mm
// 材料: 2x4
// 接合: ダボ (8x30)

// ============================================================================
// ピース
// ============================================================================

// 脚 (4本)
// 高さ = 600mm (テーブル全高、幕板は上端揃え)
(leg_fl:2x4 =600)  // 前左
(leg_fr:2x4 =600)  // 前右
(leg_bl:2x4 =600)  // 後左
(leg_br:2x4 =600)  // 後右

// 幕板
// 前後の長さ = 500 - 2*89 = 322mm (幅から脚幅2本分を引く)
// 左右の長さ = 400 - 2*38 = 324mm (奥行から脚厚2本分を引く)
(apron_front:2x4 =322)
(apron_back:2x4 =322)
(apron_left:2x4 =324)
(apron_right:2x4 =324)

// 天板ピース (奥行方向に配置)
// 各ピースは400mm長 (全奥行)
// 枚数: floor(322 / 89) = 3枚（隙間あり）
(top_1:2x4 =400)
(top_2:2x4 =400)
(top_3:2x4 =400)

// ============================================================================
// 接続
// ============================================================================

// 前幕板と脚 (上端揃え)
leg_fl -[LB>0 DB>0 D(:8x30)]- apron_front
leg_fr -[RF>0 TF>0 D(:8x30)]- apron_front

// 後幕板と脚
leg_bl -[LB>0 DB>0 D(:8x30)]- apron_back
leg_br -[RF>0 TF>0 D(:8x30)]- apron_back

// 左幕板と脚
leg_fl -[BR>0 DB<0 D(:8x30)]- apron_left
leg_bl -[FR>0 TB<0 D(:8x30)]- apron_left

// 右幕板と脚
leg_fr -[BL>0 DF<0 D(:8x30)]- apron_right
leg_br -[FL>0 TF<0 D(:8x30)]- apron_right

// 天板接続 (前幕板に)
apron_front -[RF<0 BT<0 D(:8x30)]- top_1
apron_front -[RF<116.5 BT<0 D(:8x30)]- top_2
apron_front -[RF<233 BT<0 D(:8x30)]- top_3
```

### 例2: Pythonコード出力

```python
"""シンプルサイドテーブル
寸法: 500mm x 400mm x 600mm
材料: 2x4
接合: ダボ (8x30)
"""

from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.geometry import FromMax, FromMin
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.dowel import Dowel, as_spec

# ============================================================================
# 寸法
# ============================================================================
TABLE_WIDTH = 500.0   # mm
TABLE_DEPTH = 400.0   # mm
TABLE_HEIGHT = 600.0  # mm

# 木材寸法
LUMBER_WIDTH = get_shape(PieceType.PT_2x4).width    # 89mm
LUMBER_HEIGHT = get_shape(PieceType.PT_2x4).height  # 38mm

# 計算された長さ
APRON_FRONT_BACK = TABLE_WIDTH - 2 * LUMBER_WIDTH   # 322mm
APRON_LEFT_RIGHT = TABLE_DEPTH - 2 * LUMBER_HEIGHT  # 324mm

# 接合仕様
DOWEL_SPEC = as_spec(Dowel.D8_L30)

# ============================================================================
# ピース
# ============================================================================

# 脚
leg_fl = Piece.of(PieceType.PT_2x4, TABLE_HEIGHT, "leg_fl")
leg_fr = Piece.of(PieceType.PT_2x4, TABLE_HEIGHT, "leg_fr")
leg_bl = Piece.of(PieceType.PT_2x4, TABLE_HEIGHT, "leg_bl")
leg_br = Piece.of(PieceType.PT_2x4, TABLE_HEIGHT, "leg_br")

# 幕板
apron_front = Piece.of(PieceType.PT_2x4, APRON_FRONT_BACK, "apron_front")
apron_back = Piece.of(PieceType.PT_2x4, APRON_FRONT_BACK, "apron_back")
apron_left = Piece.of(PieceType.PT_2x4, APRON_LEFT_RIGHT, "apron_left")
apron_right = Piece.of(PieceType.PT_2x4, APRON_LEFT_RIGHT, "apron_right")

# 天板ピース
top_1 = Piece.of(PieceType.PT_2x4, TABLE_DEPTH, "top_1")
top_2 = Piece.of(PieceType.PT_2x4, TABLE_DEPTH, "top_2")
top_3 = Piece.of(PieceType.PT_2x4, TABLE_DEPTH, "top_3")

# ============================================================================
# 接続
# ============================================================================
connections = []

# 前幕板接続
connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=leg_fl,
        anchor=Anchor(contact_face="left", edge_shared_face="back", offset=FromMax(value=0))
    ),
    target=BoundAnchor(
        piece=apron_front,
        anchor=Anchor(contact_face="down", edge_shared_face="back", offset=FromMax(value=0))
    ),
    spec=DOWEL_SPEC,
))

connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=leg_fr,
        anchor=Anchor(contact_face="right", edge_shared_face="front", offset=FromMax(value=0))
    ),
    target=BoundAnchor(
        piece=apron_front,
        anchor=Anchor(contact_face="top", edge_shared_face="front", offset=FromMax(value=0))
    ),
    spec=DOWEL_SPEC,
))

# 後幕板接続
connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=leg_bl,
        anchor=Anchor(contact_face="left", edge_shared_face="back", offset=FromMax(value=0))
    ),
    target=BoundAnchor(
        piece=apron_back,
        anchor=Anchor(contact_face="down", edge_shared_face="back", offset=FromMax(value=0))
    ),
    spec=DOWEL_SPEC,
))

connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=leg_br,
        anchor=Anchor(contact_face="right", edge_shared_face="front", offset=FromMax(value=0))
    ),
    target=BoundAnchor(
        piece=apron_back,
        anchor=Anchor(contact_face="top", edge_shared_face="front", offset=FromMax(value=0))
    ),
    spec=DOWEL_SPEC,
))

# 左幕板接続
connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=leg_fl,
        anchor=Anchor(contact_face="back", edge_shared_face="right", offset=FromMax(value=0))
    ),
    target=BoundAnchor(
        piece=apron_left,
        anchor=Anchor(contact_face="down", edge_shared_face="back", offset=FromMin(value=0))
    ),
    spec=DOWEL_SPEC,
))

connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=leg_bl,
        anchor=Anchor(contact_face="front", edge_shared_face="right", offset=FromMax(value=0))
    ),
    target=BoundAnchor(
        piece=apron_left,
        anchor=Anchor(contact_face="top", edge_shared_face="back", offset=FromMin(value=0))
    ),
    spec=DOWEL_SPEC,
))

# 右幕板接続
connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=leg_fr,
        anchor=Anchor(contact_face="back", edge_shared_face="left", offset=FromMax(value=0))
    ),
    target=BoundAnchor(
        piece=apron_right,
        anchor=Anchor(contact_face="down", edge_shared_face="front", offset=FromMin(value=0))
    ),
    spec=DOWEL_SPEC,
))

connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=leg_br,
        anchor=Anchor(contact_face="front", edge_shared_face="left", offset=FromMax(value=0))
    ),
    target=BoundAnchor(
        piece=apron_right,
        anchor=Anchor(contact_face="top", edge_shared_face="front", offset=FromMin(value=0))
    ),
    spec=DOWEL_SPEC,
))

# 天板接続
top_offset = (APRON_FRONT_BACK - 3 * LUMBER_WIDTH) / 2  # 3枚を中央揃え
connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=apron_front,
        anchor=Anchor(contact_face="right", edge_shared_face="front", offset=FromMin(value=0))
    ),
    target=BoundAnchor(
        piece=top_1,
        anchor=Anchor(contact_face="back", edge_shared_face="top", offset=FromMin(value=0))
    ),
    spec=DOWEL_SPEC,
))

connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=apron_front,
        anchor=Anchor(contact_face="right", edge_shared_face="front", offset=FromMin(value=LUMBER_WIDTH + top_offset))
    ),
    target=BoundAnchor(
        piece=top_2,
        anchor=Anchor(contact_face="back", edge_shared_face="top", offset=FromMin(value=0))
    ),
    spec=DOWEL_SPEC,
))

connections.append(Connection.of_dowel(
    base=BoundAnchor(
        piece=apron_front,
        anchor=Anchor(contact_face="right", edge_shared_face="front", offset=FromMin(value=2 * LUMBER_WIDTH + 2 * top_offset))
    ),
    target=BoundAnchor(
        piece=top_3,
        anchor=Anchor(contact_face="back", edge_shared_face="top", offset=FromMin(value=0))
    ),
    spec=DOWEL_SPEC,
))

# ============================================================================
# モデル構築
# ============================================================================
model = Model.of(
    pieces=[
        leg_fl, leg_fr, leg_bl, leg_br,
        apron_front, apron_back, apron_left, apron_right,
        top_1, top_2, top_3,
    ],
    connections=connections,
    label="simple_side_table",
)

# ============================================================================
# アセンブリ作成
# ============================================================================
assembly = Assembly.of(model)

print(f"シンプルサイドテーブル: {TABLE_WIDTH}mm x {TABLE_DEPTH}mm x {TABLE_HEIGHT}mm")
print(f"ピース数: {len(model.pieces)}, 接続数: {len(model.connections)}")

# オプション: build123dで可視化
# from nichiyou_daiku.shell import assembly_to_build123d
# from ocp_vscode import show
# compound = assembly_to_build123d(assembly, fillet_radius=2.0)
# show(compound)
```

---

## 使用上のヒント

### 最良の結果を得るために

1. **寸法を具体的に** - mm単位で正確な測定値を提供
2. **脚の配置を明確に** - 「内側配置」は脚がフレームの内側、「フラッシュ」は端に揃える
3. **接合の好みを指定** - 用途に応じた異なる接合（強度にはダボ、簡単な分解にはビス）
4. **構造を説明** - 棚の位置、筋交いの場所などを記述

### 一般的なパターン

| パターン | 説明 | 典型的な構造 |
|----------|------|--------------|
| テーブル | 脚の上の平らな天板 | 4本の脚 + 4枚の幕板 + 天板 |
| 棚 | 複数の水平面 | 4本の脚 + 各棚レベルに幕板 |
| ベンチ | 低くて頑丈な座席 | 4本の脚 + 貫 + 座板 |
| ラック | オープン収納 | 脚 + 筋交い + オプションの面 |

### トラブルシューティング

生成されたコードが動作しない場合：
1. 全てのピースIDがユニークであることを確認
2. 面の組み合わせが隣接している（対向ではない）ことを確認
3. オフセットがピース寸法を超えていないことを確認
4. ビスの場合、ターゲットのcontact_faceが'front'または'back'であることを確認

---

## クイックリファレンスカード

### 面の名前
```
       top (T) 上面
           │
left (L) ──┼── right (R)
  左面     │     右面
        down (D) 下面

back (B) ──┼── front (F)
  背面           前面
```

### オフセット表記
```
<n = FromMin(n)  // 開始からnmm
>n = FromMax(n)  // 終端からnmm
```

### 接続形式
```
base -[XY<offset XY<offset TYPE]- target

X = contact_face (T/D/L/R/F/B)
Y = edge_shared_face (T/D/L/R/F/B)
TYPE = V (バニラ) | D(:DxL) (ダボ) | S(Type:DxL) (ビス)
```

### 木材寸法 (mm)
```
2x4: 幅=89, 高さ=38
1x4: 幅=89, 高さ=19
```
