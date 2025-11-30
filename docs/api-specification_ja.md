# nichiyou-daiku API仕様書

本ドキュメントはnichiyou-daiku木工CADライブラリのPython APIについて説明します。

## 目次

- [概要](#概要)
- [コアモジュール](#コアモジュール)
  - [Piece（木材ピース）](#piece木材ピース)
  - [Anchor（アンカー）](#anchorアンカー)
  - [Connection（接続）](#connection接続)
  - [Model（モデル）](#modelモデル)
  - [Assembly（組み立て）](#assembly組み立て)
- [ジオメトリモジュール](#ジオメトリモジュール)
  - [Offset（オフセット）](#offsetオフセット)
  - [Face（面）](#face面)
- [ファスナー仕様](#ファスナー仕様)
  - [Dowel（ダボ）](#dowelダボ)
  - [Screw（ビス）](#screwビス)
- [DSLモジュール](#dslモジュール)
- [Shellモジュール](#shellモジュール)
- [完全な例](#完全な例)

## 概要

nichiyou-daikuは「関数型コア、命令型シェル」アーキテクチャに従います：

- **Core**: 純粋なデータモデルとビジネスロジック
- **Shell**: 外部連携（3Dエクスポート、レポート生成）
- **DSL**: ドメイン固有言語パーサー

```
nichiyou_daiku/
├── core/           # 純粋なデータモデル
│   ├── piece.py    # 木材ピース定義
│   ├── anchor.py   # 接続点仕様
│   ├── connection.py # 接続定義
│   ├── model.py    # プロジェクトモデル
│   ├── assembly/   # 3D組み立て
│   ├── dowel.py    # ダボ仕様
│   ├── screw.py    # ビス仕様
│   └── geometry/   # 幾何学プリミティブ
├── dsl/            # DSLパーサー
└── shell/          # 外部連携
```

## コアモジュール

### Piece（木材ピース）

特定のタイプと長さを持つ木材ピース。

#### PieceType

サポートされる木材タイプの列挙型。

```python
from nichiyou_daiku.core.piece import PieceType

class PieceType(Enum):
    PT_2x4 = "2x4"  # 89mm × 38mm 断面
    PT_1x4 = "1x4"  # 89mm × 19mm 断面
```

**メソッド:**

| メソッド | 説明 |
|---------|------|
| `PieceType.of(value: str)` | 文字列から作成（例: "2x4"） |

**例:**

```python
>>> PieceType.of("2x4")
<PieceType.PT_2x4: '2x4'>

>>> PieceType.of("1x4")
<PieceType.PT_1x4: '1x4'>
```

#### Piece

木材ピースを表現するクラス。

```python
from nichiyou_daiku.core.piece import Piece, PieceType

class Piece(BaseModel, frozen=True):
    id: str              # 一意の識別子
    type: PieceType      # 木材タイプ
    length: float        # 長さ（ミリメートル）
```

**ファクトリメソッド:**

| メソッド | 説明 |
|---------|------|
| `Piece.of(piece_type, length, id_=None)` | ピースを作成（id_未指定時はUUID自動生成） |

**例:**

```python
>>> piece = Piece.of(PieceType.PT_2x4, 1000.0, "leg-1")
>>> piece.id
'leg-1'
>>> piece.type
<PieceType.PT_2x4: '2x4'>
>>> piece.length
1000.0
```

#### get_shape

ピースまたはピースタイプの寸法を取得。

```python
from nichiyou_daiku.core.piece import get_shape

# オーバーロード関数:
# - get_shape(PieceType) -> Shape2D (断面)
# - get_shape(Piece) -> Shape3D (長さを含む)
```

**例:**

```python
>>> shape2d = get_shape(PieceType.PT_2x4)
>>> shape2d.width   # mm
89.0
>>> shape2d.height  # mm
38.0

>>> piece = Piece.of(PieceType.PT_2x4, 1000.0)
>>> shape3d = get_shape(piece)
>>> shape3d.width
89.0
>>> shape3d.height
38.0
>>> shape3d.length
1000.0
```

### Anchor（アンカー）

ピース上の接続点を指定。

#### Anchor

ピース面上の接続位置を定義。

```python
from nichiyou_daiku.core.anchor import Anchor
from nichiyou_daiku.core.geometry import FromMin, FromMax

class Anchor(BaseModel, frozen=True):
    contact_face: Face        # 他のピースと接触する面
    edge_shared_face: Face    # エッジを共有する面
    offset: Offset            # 共有エッジ上の位置
```

**接続モデル:**

2つのピースは常にエッジを共有して接続します。アンカーは以下を定義します：
1. `contact_face`: どの面が他のピースと接触するか
2. `edge_shared_face`: 接触面のどのエッジが揃えられるか
3. `offset`: そのエッジ上の位置

```
      edge_shared_face = "front"
              ↓
    ┌─────────┼─────────┐
    │         │         │
    │   contact_face    │  ← ピースA
    │      = "top"      │
    └─────────┴─────────┘
              │
    ┌─────────┴─────────┐
    │   contact_face    │
    │     = "down"      │  ← ピースB
    └───────────────────┘
```

**有効な面の組み合わせ:**

`contact_face`と`edge_shared_face`は隣接している必要があります（対向不可）：

| 有効 | 無効 |
|------|------|
| top + front | top + down |
| left + back | left + right |
| down + left | front + back |

**ファクトリメソッド:**

| メソッド | 説明 |
|---------|------|
| `Anchor.of(contact_face, edge_shared_face, offset)` | バリデーション付きで作成 |

**例:**

```python
>>> anchor = Anchor(
...     contact_face="front",
...     edge_shared_face="top",
...     offset=FromMax(value=100)
... )
>>> anchor.contact_face
'front'
```

#### BoundAnchor

特定のピースにバインドされたアンカー。

```python
from nichiyou_daiku.core.anchor import BoundAnchor

class BoundAnchor(BaseModel, frozen=True):
    piece: Piece    # このアンカーが属するピース
    anchor: Anchor  # アンカー位置
```

**ファクトリメソッド:**

| メソッド | 説明 |
|---------|------|
| `BoundAnchor.of(piece, anchor)` | オフセットバリデーション付きで作成 |

**例:**

```python
>>> piece = Piece.of(PieceType.PT_2x4, 1000.0, "leg-1")
>>> anchor = Anchor(
...     contact_face="front",
...     edge_shared_face="top",
...     offset=FromMax(value=100)
... )
>>> bound = BoundAnchor(piece=piece, anchor=anchor)
```

### Connection（接続）

2つのピースの接続方法を定義。

#### 接続タイプ

```python
from nichiyou_daiku.core.connection import (
    VanillaConnection,
    DowelConnection,
    ScrewConnection,
    ConnectionType,
)

class VanillaConnection(BaseModel, frozen=True):
    """補強なしの基本接続"""
    pass

class DowelConnection(BaseModel, frozen=True):
    """ダボで補強された接続"""
    radius: float  # ダボ半径（mm）
    depth: float   # ダボ深さ（mm）

class ScrewConnection(BaseModel, frozen=True):
    """ビスで補強された接続"""
    diameter: float  # ビス径（mm）
    length: float    # ビス長さ（mm）

ConnectionType = VanillaConnection | DowelConnection | ScrewConnection
```

#### Connection

2つのピース間の完全な接続仕様。

```python
from nichiyou_daiku.core.connection import Connection

class Connection(BaseModel, frozen=True):
    base: BoundAnchor           # ベースピース（固定）
    target: BoundAnchor         # ターゲットピース（ベースに接続）
    type: ConnectionType        # 接続タイプ（デフォルト: VanillaConnection）
```

**ファクトリメソッド:**

| メソッド | 説明 |
|---------|------|
| `Connection.of_vanilla(base, target)` | バニラ接続を作成 |
| `Connection.of_dowel(base, target, spec)` | ダボ接続を作成 |
| `Connection.of_screw(base, target, spec)` | ビス接続を作成 |

**例:**

```python
>>> from nichiyou_daiku.core.dowel import Dowel, as_spec

>>> conn = Connection(
...     base=BoundAnchor(piece=piece1, anchor=anchor1),
...     target=BoundAnchor(piece=piece2, anchor=anchor2),
... )

# ダボ接続
>>> conn = Connection.of_dowel(
...     base=BoundAnchor(piece=piece1, anchor=anchor1),
...     target=BoundAnchor(piece=piece2, anchor=anchor2),
...     spec=as_spec(Dowel.D8_L30),
... )
```

### Model（モデル）

ピースと接続を含む完全なプロジェクトモデル。

```python
from nichiyou_daiku.core.model import Model

class Model(BaseModel, frozen=True):
    pieces: dict[str, Piece]                      # ピースID -> Piece
    connections: dict[tuple[str, str], Connection] # (base_id, target_id) -> Connection
    label: str | None = None                       # オプションのプロジェクトラベル
```

**ファクトリメソッド:**

| メソッド | 説明 |
|---------|------|
| `Model.of(pieces, connections, label=None)` | イテラブルから作成 |

**例:**

```python
>>> piece1 = Piece.of(PieceType.PT_2x4, 1000.0, "piece-1")
>>> piece2 = Piece.of(PieceType.PT_2x4, 800.0, "piece-2")
>>> conn = Connection(
...     base=BoundAnchor(piece=piece1, anchor=anchor1),
...     target=BoundAnchor(piece=piece2, anchor=anchor2),
... )
>>> model = Model.of(
...     pieces=[piece1, piece2],
...     connections=[conn],
...     label="マイテーブル"
... )
>>> len(model.pieces)
2
>>> ("piece-1", "piece-2") in model.connections
True
```

### Assembly（組み立て）

ジョイント位置と向きを含む3D組み立て情報。

```python
from nichiyou_daiku.core.assembly import Assembly

class Assembly(BaseModel, frozen=True):
    model: Model                              # ソースモデル
    boxes: dict[str, Box]                     # ピースID -> 3Dバウンディングボックス
    joints: dict[str, Joint]                  # ジョイントID -> Joint
    joint_conns: list[tuple[str, str]]        # 接続されたジョイントIDペア
    pilot_holes: dict[str, list[tuple[Point3D, Hole]]]  # ピースID -> 穴
    label: str | None                         # オプションのラベル
```

**ファクトリメソッド:**

| メソッド | 説明 |
|---------|------|
| `Assembly.of(model)` | モデルから3D組み立てを作成 |

**例:**

```python
>>> assembly = Assembly.of(model)
>>> len(assembly.joints)
2  # 1つのジョイントペアは2つのジョイントを作成
>>> len(assembly.joint_conns)
1
```

## ジオメトリモジュール

### Offset（オフセット）

エッジ上の位置、両端どちらからでも測定可能。

```python
from nichiyou_daiku.core.geometry import FromMin, FromMax, Offset

class FromMin(BaseModel, frozen=True):
    """最小（開始）位置からのオフセット"""
    value: float  # 距離（mm）

class FromMax(BaseModel, frozen=True):
    """最大（終了）位置からのオフセット"""
    value: float  # 距離（mm）

Offset = FromMin | FromMax
```

**例:**

```python
>>> offset1 = FromMin(value=100)  # 開始から100mm
>>> offset2 = FromMax(value=50)   # 終端から50mm
```

### Face（面）

矩形ピースの6つの面。

```python
Face = Literal["top", "down", "left", "right", "front", "back"]
```

**面の図:**

```
        top（上面）
           │
  left ────┼──── right
（左面）    │    （右面）
         down（下面）

  back ────┼──── front
（背面）         （前面）
```

**ユーティリティ関数:**

| 関数 | 説明 |
|------|------|
| `opposite(face)` | 対向面を取得 |
| `cross(face1, face2)` | 垂直な面を取得 |
| `is_adjacent(face1, face2)` | 隣接しているか確認 |

## ファスナー仕様

### Dowel（ダボ）

標準的な木製ダボサイズ。

```python
from nichiyou_daiku.core.dowel import Dowel, DowelSpec, as_spec

class DowelSpec(BaseModel, frozen=True):
    diameter: float  # mm
    length: float    # mm

class Dowel(Enum):
    D6_L25 = "6x25"
    D6_L30 = "6x30"
    D8_L25 = "8x25"
    D8_L30 = "8x30"
    D8_L40 = "8x40"
    D10_L30 = "10x30"
    D10_L40 = "10x40"
    D12_L40 = "12x40"
```

**関数:**

| 関数 | 説明 |
|------|------|
| `Dowel.of(value)` | 文字列から作成（例: "8x30"） |
| `as_spec(dowel)` | プリセットをDowelSpecに変換 |

**例:**

```python
>>> dowel = Dowel.of("8x30")
>>> spec = as_spec(dowel)
>>> spec.diameter
8.0
>>> spec.length
30.0
```

### Screw（ビス）

スリムビスとコーススレッドを含む標準ビスサイズ。

```python
from nichiyou_daiku.core.screw import (
    ScrewSpec,
    SlimScrew,
    CoarseThreadScrew,
    as_spec,
)

class ScrewSpec(BaseModel, frozen=True):
    diameter: float  # mm
    length: float    # mm

class SlimScrew(Enum):
    D3_3_L25 = "3.3x25"
    D3_3_L30 = "3.3x30"
    D3_3_L35 = "3.3x35"
    D3_3_L40 = "3.3x40"
    D3_3_L45 = "3.3x45"
    D3_3_L50 = "3.3x50"
    D3_8_L55 = "3.8x55"
    D3_8_L60 = "3.8x60"
    D3_8_L65 = "3.8x65"
    D3_8_L70 = "3.8x70"
    D3_8_L75 = "3.8x75"
    D4_2_L90 = "4.2x90"

class CoarseThreadScrew(Enum):
    D3_8_L25 = "3.8x25"
    D3_8_L30 = "3.8x30"
    D3_8_L35 = "3.8x35"
    D3_8_L40 = "3.8x40"
    D3_8_L45 = "3.8x45"
    D3_8_L50 = "3.8x50"
    D3_8_L57 = "3.8x57"
    D4_2_L65 = "4.2x65"
    D4_2_L75 = "4.2x75"
    D4_5_L90 = "4.5x90"
    D4_5_L100 = "4.5x100"
    D5_2_L120 = "5.2x120"
```

**関数:**

| 関数 | 説明 |
|------|------|
| `SlimScrew.of(value)` | 文字列から作成（例: "3.3x50"） |
| `CoarseThreadScrew.of(value)` | 文字列から作成（例: "3.8x57"） |
| `as_spec(screw)` | プリセットをScrewSpecに変換 |

**例:**

```python
>>> screw = SlimScrew.of("3.3x50")
>>> spec = as_spec(screw)
>>> spec.diameter
3.3
>>> spec.length
50.0
```

## DSLモジュール

`.nd`ファイルをModelオブジェクトにパース。

```python
from nichiyou_daiku.dsl import (
    parse_dsl,
    DSLError,
    DSLSyntaxError,
    DSLSemanticError,
    DSLValidationError,
)
```

**関数:**

| 関数 | 説明 |
|------|------|
| `parse_dsl(source: str) -> Model` | DSL文字列をModelにパース |

**例外:**

| 例外 | 説明 |
|------|------|
| `DSLError` | 全DSLエラーの基底例外 |
| `DSLSyntaxError` | 構文エラー |
| `DSLSemanticError` | 参照エラー（例: 未知のピース） |
| `DSLValidationError` | 値エラー（例: 未知のプリセット） |

**例:**

```python
>>> dsl = """
... (leg:2x4 =720)
... (apron:2x4 =600)
... leg -[FR>100 DB<0]- apron
... """
>>> model = parse_dsl(dsl)
>>> len(model.pieces)
2
```

完全な構文リファレンスは[DSL仕様書](./dsl-specification_ja.md)を参照してください。

## Shellモジュール

3Dエクスポートとレポートのための外部連携。

### リソース抽出

```python
from nichiyou_daiku.shell import (
    extract_resources,
    ResourceSummary,
    PieceResource,
)

def extract_resources(assembly: Assembly) -> ResourceSummary:
    """組み立てから部品表を抽出"""
```

**例:**

```python
>>> resources = extract_resources(assembly)
>>> resources.pretty_print()
```

### レポート生成

```python
from nichiyou_daiku.shell import generate_markdown_report

def generate_markdown_report(
    resources: ResourceSummary,
    project_name: str = "Woodworking Project",
    standard_lengths: dict[PieceType, list[float]] | None = None,
    include_cut_diagram: bool = True,
) -> str:
    """カット最適化付きMarkdownレポートを生成"""
```

**例:**

```python
>>> report = generate_markdown_report(
...     resources,
...     project_name="マイテーブル",
...     include_cut_diagram=True,
... )
>>> print(report)
```

### 3Dエクスポート（オプション）

`build123d`パッケージが必要。

```python
from nichiyou_daiku.shell import assembly_to_build123d

def assembly_to_build123d(
    assembly: Assembly,
    fillet_radius: float = 5.0,
) -> "Compound":
    """3D可視化用にアセンブリをbuild123d Compoundに変換"""
```

**例:**

```python
>>> compound = assembly_to_build123d(assembly, fillet_radius=2.0)
>>> # ocp-vscodeで使用するか、STL/STEPにエクスポート
```

## 完全な例

### シンプルテーブル

```python
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.geometry import FromMin, FromMax

# ピースを作成
leg1 = Piece.of(PieceType.PT_2x4, 720.0, "leg1")
leg2 = Piece.of(PieceType.PT_2x4, 720.0, "leg2")
apron = Piece.of(PieceType.PT_2x4, 600.0, "apron")

# 接続を定義
connections = [
    Connection(
        base=BoundAnchor(
            piece=leg1,
            anchor=Anchor(
                contact_face="front",
                edge_shared_face="right",
                offset=FromMax(value=100)
            )
        ),
        target=BoundAnchor(
            piece=apron,
            anchor=Anchor(
                contact_face="down",
                edge_shared_face="back",
                offset=FromMin(value=0)
            )
        )
    ),
    Connection(
        base=BoundAnchor(
            piece=leg2,
            anchor=Anchor(
                contact_face="front",
                edge_shared_face="left",
                offset=FromMax(value=100)
            )
        ),
        target=BoundAnchor(
            piece=apron,
            anchor=Anchor(
                contact_face="down",
                edge_shared_face="back",
                offset=FromMax(value=0)
            )
        )
    ),
]

# モデルとアセンブリを作成
model = Model.of(
    pieces=[leg1, leg2, apron],
    connections=connections,
    label="シンプルテーブル"
)
assembly = Assembly.of(model)
```

### DSLを使用

```python
from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.core.assembly import Assembly

dsl = """
// ダボ接合のシンプルテーブル
(leg1:2x4 =720)
(leg2:2x4 =720)
(apron:2x4 =600)

leg1 -[FR>100 DB<0 D(:8x30)]- apron
leg2 -[FL>100 DB>0 D(:8x30)]- apron
"""

model = parse_dsl(dsl)
assembly = Assembly.of(model)
```

### ビス接続を使用

```python
from nichiyou_daiku.core.screw import SlimScrew, as_spec
from nichiyou_daiku.core.connection import Connection

conn = Connection.of_screw(
    base=BoundAnchor(piece=leg, anchor=leg_anchor),
    target=BoundAnchor(piece=apron, anchor=apron_anchor),
    spec=as_spec(SlimScrew.D3_3_L50),
)
```

または DSL を使用:

```python
dsl = """
(leg:2x4 =720)
(apron:2x4 =600)

leg -[FR>100 FB<0 S(Slim:3.3x50)]- apron
"""
```
