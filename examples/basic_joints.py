"""Basic joint types demonstration.

This example shows the fundamental joint types available in nichiyou-daiku,
demonstrating different ways pieces can be connected together.

==============================================================================
Connection Types Overview
==============================================================================
nichiyou-daikuでは3種類の接合方法（ConnectionType）をサポート:

1. VanillaConnection (デフォルト)
   - シンプルな接合、パラメータなし
   - 用途: 釘やネジを別途打つ場合など
   - Usage: Connection(...) または Connection.of_vanilla(...)

2. DowelConnection
   - ダボ接合
   - パラメータ: radius (ダボ半径mm), depth (ダボ深さmm)
   - 2本のダボが自動配置される
   - Usage: Connection.of_dowel(..., radius=4.0, depth=20.0)

3. ScrewConnection (新規追加)
   - ネジ接合
   - パラメータ: diameter (ネジ径mm), length (ネジ長さmm)
   - Target側は貫通穴、Base側はねじ込み深さで穴生成
   - 制約: Target側contact_faceはfront/backのみ
   - Usage: Connection.of_screw(..., diameter=4.0, length=50.0)

==============================================================================
"""

from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.anchor import Anchor
from nichiyou_daiku.core.anchor import BoundAnchor
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.geometry import FromMax, FromMin
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.screw import ScrewSpec, CoarseThreadScrew, as_spec
from nichiyou_daiku.shell import assembly_to_build123d
from build123d import Location
from ocp_vscode import show_object

# We'll create multiple joint examples, showing them separately

# ==============================================================================
# Example 1: T-Joint (perpendicular connection in the middle of a piece)
# ==============================================================================
print("Building T-Joint example...")

# Create pieces for T-joint
base_beam = Piece.of(PieceType.PT_2x4, 800.0, "t_base")  # Horizontal base
upright = Piece.of(PieceType.PT_2x4, 400.0, "t_upright")  # Vertical piece

# T-Joint: Connect upright to the middle of base beam
t_joint_connection = Connection(
    base=BoundAnchor(
        piece=base_beam,
        anchor=Anchor(
            contact_face="front",
            edge_shared_face="right",
            offset=FromMin(value=400.0),  # 400mm from the edge (centered on 800mm beam)
        ),
    ),
    target=BoundAnchor(
        piece=upright,
        anchor=Anchor(
            contact_face="down",
            edge_shared_face="front",
            offset=FromMin(value=44.5),  # Centered on the 89mm width of 2x4
        ),
    ),
)

t_joint_model = Model.of(
    pieces=[base_beam, upright],
    connections=[t_joint_connection],
    label="t_joint",
)

# ==============================================================================
# Example 2: Butt Joint (end-to-end connection)
# ==============================================================================
print("Building Butt Joint example...")

# Create pieces for butt joint
first_piece = Piece.of(PieceType.PT_2x4, 300.0, "butt_first")
second_piece = Piece.of(PieceType.PT_2x4, 300.0, "butt_second")

# Butt Joint: Connect end-to-end
butt_joint_connection = Connection(
    base=BoundAnchor(
        piece=first_piece,
        anchor=Anchor(
            contact_face="top", edge_shared_face="left", offset=FromMin(value=0)
        ),
    ),
    target=BoundAnchor(
        piece=second_piece,
        anchor=Anchor(
            contact_face="down", edge_shared_face="left", offset=FromMin(value=0)
        ),
    ),
)

butt_joint_model = Model.of(
    pieces=[first_piece, second_piece],
    connections=[butt_joint_connection],
    label="butt_joint",
)

# ==============================================================================
# Example 3: Corner Joint (two pieces meeting at right angles)
# ==============================================================================
print("Building Corner Joint example...")

# Create pieces for corner joint
side_a = Piece.of(PieceType.PT_2x4, 400.0, "corner_a")
side_b = Piece.of(PieceType.PT_2x4, 400.0, "corner_b")

# Corner Joint: Two pieces meeting at 90 degrees
corner_joint_connection = Connection(
    base=BoundAnchor(
        piece=side_a,
        anchor=Anchor(
            contact_face="back", edge_shared_face="right", offset=FromMin(value=0.0)
        ),
    ),
    target=BoundAnchor(
        piece=side_b,
        anchor=Anchor(
            contact_face="left", edge_shared_face="front", offset=FromMin(value=0.0)
        ),
    ),
)

corner_joint_model = Model.of(
    pieces=[side_a, side_b],
    connections=[corner_joint_connection],
    label="corner_joint",
)

# ==============================================================================
# Example 4: Dowel Connection (ダボ接合)
# ==============================================================================
print("Building Dowel Connection example...")

# Create pieces for dowel joint
dowel_base = Piece.of(PieceType.PT_2x4, 600.0, "dowel_base")
dowel_upright = Piece.of(PieceType.PT_2x4, 300.0, "dowel_upright")

# Dowel Connection: T字接合 with 2 dowels
# of_dowel creates a connection with 2 dowel holes automatically positioned
dowel_connection = Connection.of_dowel(
    base=BoundAnchor(
        piece=dowel_base,
        anchor=Anchor(
            contact_face="front",
            edge_shared_face="right",
            offset=FromMin(value=300.0),  # Centered
        ),
    ),
    target=BoundAnchor(
        piece=dowel_upright,
        anchor=Anchor(
            contact_face="down",
            edge_shared_face="front",
            offset=FromMin(value=44.5),  # Centered on 89mm width
        ),
    ),
    radius=4.0,  # ダボ半径 4mm (直径8mm)
    depth=20.0,  # ダボ深さ 20mm (両側に20mmずつ)
)

dowel_model = Model.of(
    pieces=[dowel_base, dowel_upright],
    connections=[dowel_connection],
    label="dowel_joint",
)

# ==============================================================================
# Example 5: Screw Connection (ネジ接合)
# ==============================================================================
print("Building Screw Connection example...")

# Create pieces for screw joint
screw_base = Piece.of(PieceType.PT_2x4, 600.0, "screw_base")
screw_upright = Piece.of(PieceType.PT_2x4, 300.0, "screw_upright")

# Screw Connection: T字接合 with screws
# Note: Target側のcontact_faceはfront/backのみに制限されている
# of_screw creates:
#   - Target側: 貫通穴（ネジが通過）
#   - Base側: screw.length - target_thickness の深さの穴
#
# 方法1: 規格サイズを使う（推奨）
# screw_spec = get_spec(CoarseThreadScrew.D3_8_L57)
#
# 方法2: 任意サイズを指定
# screw_spec = ScrewSpec(diameter=4.0, length=50.0)
screw_connection = Connection.of_screw(
    base=BoundAnchor(
        piece=screw_base,
        anchor=Anchor(
            contact_face="front",
            edge_shared_face="right",
            offset=FromMin(value=300.0),  # Centered
        ),
    ),
    target=BoundAnchor(
        piece=screw_upright,
        anchor=Anchor(
            contact_face="back",  # Must be "front" or "back" for ScrewConnection
            edge_shared_face="top",
            offset=FromMin(value=44.5),  # Centered on 89mm width
        ),
    ),
    spec=as_spec(CoarseThreadScrew.D3_8_L57),  # 規格サイズ: 3.8mm径 x 57mm長
)

screw_model = Model.of(
    pieces=[screw_base, screw_upright],
    connections=[screw_connection],
    label="screw_joint",
)

# ==============================================================================
# Visualize all joints
# ==============================================================================

# Convert each model to assembly and then to build123d
print("\nConverting to 3D...")

# T-Joint (VanillaConnection)
t_assembly = Assembly.of(t_joint_model)
t_compound = assembly_to_build123d(t_assembly, fillet_radius=2.0).moved(
    Location((0, 300, 0))
)

# Butt Joint (VanillaConnection)
butt_assembly = Assembly.of(butt_joint_model)
butt_compound = assembly_to_build123d(butt_assembly, fillet_radius=2.0).moved(
    Location((0, 0, 0))
)

# Corner Joint (VanillaConnection)
corner_assembly = Assembly.of(corner_joint_model)
corner_compound = assembly_to_build123d(corner_assembly, fillet_radius=2.0).moved(
    Location((0, -300, 0))
)

# Dowel Joint (DowelConnection)
dowel_assembly = Assembly.of(dowel_model)
dowel_compound = assembly_to_build123d(dowel_assembly, fillet_radius=2.0).moved(
    Location((500, 150, 0))
)

# Screw Joint (ScrewConnection)
screw_assembly = Assembly.of(screw_model)
screw_compound = assembly_to_build123d(screw_assembly, fillet_radius=2.0).moved(
    Location((500, -150, 0))
)

# Display all joints
show_object(t_compound)
show_object(butt_compound)
show_object(corner_compound)
show_object(dowel_compound)
show_object(screw_compound)

print("\nDone! Use OCP CAD Viewer to examine the joints.")
print("Left side: Joint shapes (T, Butt, Corner) with VanillaConnection")
print("Right side: Connection types (Dowel, Screw)")
