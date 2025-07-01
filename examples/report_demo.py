"""Demonstration of report generation feature."""

from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.resources import extract_resources
from nichiyou_daiku.shell.report_generator import generate_markdown_report

# Create a simple table model
pieces = [
    # Table legs (2x4)
    Piece.of(PieceType.PT_2x4, 750.0, "leg-1"),
    Piece.of(PieceType.PT_2x4, 750.0, "leg-2"),
    Piece.of(PieceType.PT_2x4, 750.0, "leg-3"),
    Piece.of(PieceType.PT_2x4, 750.0, "leg-4"),
    
    # Aprons (2x4)
    Piece.of(PieceType.PT_2x4, 1200.0, "apron-front"),
    Piece.of(PieceType.PT_2x4, 1200.0, "apron-back"),
    Piece.of(PieceType.PT_2x4, 800.0, "apron-left"),
    Piece.of(PieceType.PT_2x4, 800.0, "apron-right"),
    
    # Tabletop pieces (1x4)
    Piece.of(PieceType.PT_1x4, 1400.0, "top-1"),
    Piece.of(PieceType.PT_1x4, 1400.0, "top-2"),
    Piece.of(PieceType.PT_1x4, 1400.0, "top-3"),
    Piece.of(PieceType.PT_1x4, 1400.0, "top-4"),
]

# Create model
model = Model.of(pieces=pieces, connections=[], label="Simple Dining Table")

# Extract resources
print("=== Report Generation Demo ===\n")
resources = extract_resources(model)

# Define custom standard lengths (metric)
custom_standard_lengths = {
    PieceType.PT_2x4: [2400.0, 3000.0, 3600.0],  # Common metric lengths
    PieceType.PT_1x4: [1800.0, 2400.0, 3000.0],  # Different for 1x4
}

# Generate report
report = generate_markdown_report(
    resources,
    project_name="Simple Dining Table",
    standard_lengths=custom_standard_lengths,
    include_cut_diagram=True
)

# Save report
filename = "dining_table_report.md"
with open(filename, "w", encoding="utf-8") as f:
    f.write(report)

print(f"✅ Report saved to: {filename}")
print("\n📋 Report Contents Preview:")
print("=" * 80)
print(report[:1200])
print("...")
print("=" * 80)

print(f"\n🔧 Total pieces: {resources.total_pieces}")
print(f"📏 Lumber types: {list(resources.pieces_by_type.keys())}")
print(f"📦 Optimized for metric standard lengths")
print(f"💾 Full report available in {filename}")