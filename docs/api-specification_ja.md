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
    PT_2x4 = "2x4"  # 89mm（幅）× 38mm（厚み）断面
    PT_1x4 = "1x4"  # 89mm（幅）× 19mm（厚み）断面
```

**メソッド:**

| メソッド | 説明 |
|---------|------|
| `PieceType.of(value: str)` | 文字列から作成（例: "2x4"） |

**例:**

```python
>>> from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
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
    length: float        # 長さ（ミリメートル、0より大きい）
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

各ピースは固有のローカル座標系を持ちます: X = 幅（`width`）、Y = 厚み（`height`）、Z = 長さ（`length`）。

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
2. `edge_shared_face`: 隣接する面。アンカーは2つの面が交わるエッジ上にある
3. `offset`: そのエッジ上の位置

エッジは2つの面の両方に垂直な軸に沿って伸びます：

| 面の組み合わせ（順不同） | エッジの方向 | エッジの長さ (2x4 / 1x4) | `FromMin(v)` の基準 | `FromMax(v)` の基準 |
|--------------------------|--------------|--------------------------|---------------------|---------------------|
| top/down + front/back | 幅方向 (X) | 89 / 89 | left側 | right側 |
| top/down + left/right | 厚み方向 (Y) | 38 / 19 | back側 | front側 |
| front/back + left/right | 長さ方向 (Z) | L / L | down端 | top端 |

オフセットがエッジの長さを超えると `BoundAnchor` は `ValueError` を送出します。

**配置:** 接続はターゲットをベースに対して次のように配置します。(1) 2つのcontact_faceが面同士で接する、(2) 2つのedge_shared_faceが同じ平面上で同じ向きを向く（面一）、(3) 2つのアンカー点が一致する。ターゲット側が `FromMin` ならターゲットの最小側の端（down/left/back）が、`FromMax` なら最大側の端（top/right/front）がその点に来ます。

例（床 z=0 に立てた2x4の脚 L=700 と2x4の幕板 L=500）: 脚のベースアンカー `front`/`left`/`FromMin(100)` と幕板のターゲットアンカー `down`/`front`/`FromMin(0)`（DSL では `leg -[FL<100 DF<0]- apron`）では、幕板のdown端が脚のfront面に接し、幕板のfront面が脚のleft面と面一になり、幕板のleft側が床から100mmの点に来るため、幕板は z=11..100 を占めます。幕板側を `FromMax(0)` にすると z=100..189 になります。

**有効な面の組み合わせ:**

`contact_face`と`edge_shared_face`は隣接している必要があります（同じ面・対向面は不可）：

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
>>> from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
>>> from nichiyou_daiku.core.geometry import FromMin, FromMax
>>> anchor = Anchor(
...     contact_face="front",
...     edge_shared_face="top",
...     offset=FromMax(value=50)
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
...     offset=FromMax(value=50)  # front/topのエッジは幅89mmの方向に伸びる
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
    depth: float   # ダボの全長（mm）。半分ずつ各ピースに入る

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

**検証**（`ValueError` を送出）: ピースを自分自身に接続することはできません。ダボ: ダボの長さの半分が、各ピースの接触面の法線方向の寸法（front/back → 厚み、left/right → 89、top/down → ピースの長さ）に収まる必要があります。ビス: ターゲットの接触面は `front` または `back` で、ターゲットの厚み < 長さ <= ベースの接触面の法線方向の寸法 + ターゲットの厚み である必要があります。

**例:**

```python
>>> from nichiyou_daiku.core.connection import Connection
>>> from nichiyou_daiku.core.dowel import Dowel, as_spec
>>> leg = Piece.of(PieceType.PT_2x4, 720.0, "leg")
>>> apron = Piece.of(PieceType.PT_2x4, 600.0, "apron")
>>> leg_anchor = Anchor(contact_face="left", edge_shared_face="back", offset=FromMax(value=0))
>>> apron_anchor = Anchor(contact_face="down", edge_shared_face="back", offset=FromMax(value=0))

>>> conn = Connection(
...     base=BoundAnchor(piece=leg, anchor=leg_anchor),
...     target=BoundAnchor(piece=apron, anchor=apron_anchor),
... )

# ダボ接続
>>> dowel_conn = Connection.of_dowel(
...     base=BoundAnchor(piece=leg, anchor=leg_anchor),
...     target=BoundAnchor(piece=apron, anchor=apron_anchor),
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

`Model.of` は、ピースIDの重複、`pieces` に含まれないピースを参照する接続、同じ (base, target) の組に対する2つ目の接続に対して `ValueError` を送出します。

**例:**

```python
>>> from nichiyou_daiku.core.model import Model
>>> model = Model.of(
...     pieces=[leg, apron],
...     connections=[conn],
...     label="マイテーブル"
... )
>>> len(model.pieces)
2
>>> ("leg", "apron") in model.connections
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
    pilot_holes: dict[str, list[tuple[SurfacePoint, Hole]]]  # ピースID -> 穴（SurfacePointは穴をあける面を示す）
    label: str | None                         # オプションのラベル
```

**ファクトリメソッド:**

| メソッド | 説明 |
|---------|------|
| `Assembly.of(model)` | モデルから3D組み立てを作成 |

**例:**

```python
>>> from nichiyou_daiku.core.assembly import Assembly
>>> assembly = Assembly.of(model)
>>> len(assembly.joints)  # 1つのバニラ接続は1つのジョイントペア（2つのジョイント）を作成
2
>>> len(assembly.joint_conns)
1
```

**下穴:** ダボ接続では各ピースにダボ径・深さ 長さ/2 の穴、ビス接続ではターゲットに貫通穴、ベースに深さ (長さ - ターゲットの厚み) の穴が追加されます。バニラ接続では穴はありません。

## ジオメトリモジュール

### Offset（オフセット）

エッジ上の位置、両端どちらからでも測定可能。

```python
from nichiyou_daiku.core.geometry import FromMin, FromMax, Offset

class FromMin(BaseModel, frozen=True):
    """エッジの最小側の端（down端 / left側 / back側）からのオフセット"""
    value: float  # 距離（mm）、0以上

class FromMax(BaseModel, frozen=True):
    """エッジの最大側の端（top端 / right側 / front側）からのオフセット"""
    value: float  # 距離（mm）、0以上

Offset = FromMin | FromMax
```

**例:**

```python
>>> offset1 = FromMin(value=100)  # 最小側の端から100mm
>>> offset2 = FromMax(value=50)   # 最大側の端から50mm
```

### Face（面）

矩形ピースの6つの面。

```python
from typing import Literal

Face = Literal["top", "down", "left", "right", "front", "back"]
```

面の名前はピースのローカル座標系（X = 幅、Y = 厚み、Z = 長さ）に基づきます：

| 面 | 法線 | 種類 | 2x4でのサイズ |
|----|------|------|---------------|
| top | +Z | 長さ方向の最大側の木口面 | 89 × 38 |
| down | -Z | 長さ方向の最小側の木口面 | 89 × 38 |
| front | +Y | 広い面 | 89 × 長さ |
| back | -Y | 広い面 | 89 × 長さ |
| right | +X | 細い面 | 38 × 長さ |
| left | -X | 細い面 | 38 × 長さ |

**面の図**（断面図。top端 = +Z を手前に向けて見た場合）:

```
                 front (+Y)
            ┌──────────────────┐
  left (-X) │                  │ right (+X)
            └──────────────────┘
                 back (-Y)
            ←─────── 89 ───────→
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
>>> from nichiyou_daiku.core.dowel import Dowel, as_spec
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
>>> from nichiyou_daiku.core.screw import SlimScrew, as_spec
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
>>> from nichiyou_daiku.dsl import parse_dsl
>>> dsl = """
... (leg:2x4 =720)
... (apron:2x4 =600)
... leg -[LB>0 DB>0]- apron
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
>>> from nichiyou_daiku.shell import extract_resources
>>> assembly = Assembly.of(model)
>>> resources = extract_resources(assembly)  # 引数はModelではなくAssembly
>>> resources.total_pieces
2
>>> summary_text = resources.pretty_print()  # 人が読める形式の概要
```

### レポート生成

```python
from nichiyou_daiku.shell import generate_markdown_report

def generate_markdown_report(
    resource_summary: ResourceSummary,
    project_name: str = "Woodworking Project",
    standard_lengths: dict[PieceType, list[float]] | None = None,
    include_cut_diagram: bool = True,
    include_anchor_details: bool = True,
    include_pilot_holes: bool = True,
) -> str:
    """カット最適化付きMarkdownレポートを生成"""
```

木取り計画では1カットごとに3mmののこ刃厚（切りしろ）を見込み、どの定尺材よりも長いピースがあれば警告します。

**例:**

```python
>>> from nichiyou_daiku.shell import generate_markdown_report
>>> report = generate_markdown_report(
...     resources,
...     project_name="マイテーブル",
...     include_cut_diagram=True,
... )
>>> report.splitlines()[0]
'# マイテーブル Report'
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
>>> from nichiyou_daiku.shell import assembly_to_build123d
>>> compound = assembly_to_build123d(assembly, fillet_radius=2.0)
>>> # ocp-vscodeで使用するか、STL/STEPにエクスポート
```

## 完全な例

### シンプルなフレーム

2本の脚と、その間に脚のtopと面一で入る幕板。

```python
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.geometry import FromMax

# ピースを作成
leg1 = Piece.of(PieceType.PT_2x4, 720.0, "leg1")
leg2 = Piece.of(PieceType.PT_2x4, 720.0, "leg2")
apron = Piece.of(PieceType.PT_2x4, 600.0, "apron")

# 接続を定義
connections = [
    # leg1 -[LB>0 DB>0]- apron
    Connection(
        base=BoundAnchor(
            piece=leg1,
            anchor=Anchor(
                contact_face="left",
                edge_shared_face="back",
                offset=FromMax(value=0)
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
    # leg2 -[RF>0 TF>0]- apron
    Connection(
        base=BoundAnchor(
            piece=leg2,
            anchor=Anchor(
                contact_face="right",
                edge_shared_face="front",
                offset=FromMax(value=0)
            )
        ),
        target=BoundAnchor(
            piece=apron,
            anchor=Anchor(
                contact_face="top",
                edge_shared_face="front",
                offset=FromMax(value=0)
            )
        )
    ),
]

# モデルとアセンブリを作成（全体 778 × 38 × 720mm）
model = Model.of(
    pieces=[leg1, leg2, apron],
    connections=connections,
    label="シンプルなフレーム"
)
assembly = Assembly.of(model)
```

### DSLを使用

```python
from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.core.assembly import Assembly

dsl = """
// ダボ接合のシンプルなフレーム
(leg1:2x4 =720)
(leg2:2x4 =720)
(apron:2x4 =600)

leg1 -[LB>0 DB>0 D(:8x30)]- apron
leg2 -[RF>0 TF>0 D(:8x30)]- apron
"""

model = parse_dsl(dsl)
assembly = Assembly.of(model)
```

### ビス接続を使用

ビスはターゲット（接触面が `front` または `back`）を貫通してベースに打ち込まれます。

```python
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.geometry import FromMin
from nichiyou_daiku.core.screw import SlimScrew, as_spec

post = Piece.of(PieceType.PT_2x4, 600.0, "post")
rail = Piece.of(PieceType.PT_2x4, 400.0, "rail")

# 柱のdown端から300mmの位置で、柱のfront面に横木をビス留め
conn = Connection.of_screw(
    base=BoundAnchor(
        piece=post,
        anchor=Anchor(contact_face="front", edge_shared_face="left", offset=FromMin(value=300)),
    ),
    target=BoundAnchor(
        piece=rail,
        anchor=Anchor(contact_face="back", edge_shared_face="top", offset=FromMin(value=0)),
    ),
    spec=as_spec(SlimScrew.D3_3_L50),
)
```

または DSL を使用:

```python
from nichiyou_daiku.dsl import parse_dsl

dsl = """
(post:2x4 =600)
(rail:2x4 =400)

post -[FL<300 BT<0 S(Slim:3.3x50)]- rail
"""
model = parse_dsl(dsl)
```
