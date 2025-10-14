"""Simple demonstration of resource extraction feature."""

from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.shell import extract_resources

# Create a simple furniture model
pieces = [
    # Table legs
    Piece.of(PieceType.PT_2x4, 750.0, "leg-1"),
    Piece.of(PieceType.PT_2x4, 750.0, "leg-2"),
    Piece.of(PieceType.PT_2x4, 750.0, "leg-3"),
    Piece.of(PieceType.PT_2x4, 750.0, "leg-4"),
    
    # Aprons
    Piece.of(PieceType.PT_2x4, 1200.0, "apron-front"),
    Piece.of(PieceType.PT_2x4, 1200.0, "apron-back"),
    Piece.of(PieceType.PT_2x4, 600.0, "apron-left"),
    Piece.of(PieceType.PT_2x4, 600.0, "apron-right"),
    
    # Tabletop pieces (using 1x4)
    Piece.of(PieceType.PT_1x4, 1400.0, "top-1"),
    Piece.of(PieceType.PT_1x4, 1400.0, "top-2"),
    Piece.of(PieceType.PT_1x4, 1400.0, "top-3"),
    Piece.of(PieceType.PT_1x4, 1400.0, "top-4"),
    Piece.of(PieceType.PT_1x4, 1400.0, "top-5"),
]

# Create model (connections not needed for resource extraction)
model = Model.of(pieces=pieces, connections=[], label="Simple Table")

# Create assembly and extract resources
print("=== Resource Extraction Demo ===\n")
assembly = Assembly.of(model)
resources = extract_resources(assembly)

# Display pretty print summary
print(resources.pretty_print())

# Show JSON export
print("\n\n=== JSON Export ===")
json_output = resources.model_dump_json(indent=2)
print(json_output)

# Show shopping list format
print("\n\n=== Shopping List ===")
print("To build this table, you need:")
for piece_type, count in resources.pieces_by_type.items():
    total_length = resources.total_length_by_type[piece_type]
    # Convert to meters for easier reading
    length_m = total_length / 1000
    print(f"- {piece_type.value}: {count} pieces, total {length_m:.1f} meters")

# Calculate standard lumber needs (assuming 2.4m standard length)
print("\n=== Standard Lumber Purchase ===")
standard_length = 2400.0  # 2.4m in mm
for piece_type, total_length in resources.total_length_by_type.items():
    boards_needed = int(total_length / standard_length) + (1 if total_length % standard_length > 0 else 0)
    print(f"- {piece_type.value} boards (2.4m each): {boards_needed}")