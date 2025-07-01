"""Tests for resource extraction module."""

import json

import pytest

from nichiyou_daiku.core.model import Model, PiecePair
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.connection import Connection, Anchor
from nichiyou_daiku.core.geometry import FromMax, FromMin
from nichiyou_daiku.core.resources import (
    PieceResource,
    ResourceSummary,
    extract_resources,
)


class TestPieceResource:
    """Test PieceResource model."""

    def test_should_create_piece_resource(self):
        """Should create a PieceResource with all properties."""
        resource = PieceResource(
            id="test-piece",
            type=PieceType.PT_2x4,
            length=1000.0,
            width=89.0,
            height=38.0,
            volume=3_382_000.0,
        )

        assert resource.id == "test-piece"
        assert resource.type == PieceType.PT_2x4
        assert resource.length == 1000.0
        assert resource.width == 89.0
        assert resource.height == 38.0
        assert resource.volume == 3_382_000.0

    def test_should_serialize_to_json(self):
        """Should serialize PieceResource to JSON with PieceType as string."""
        resource = PieceResource(
            id="test-piece",
            type=PieceType.PT_2x4,
            length=1000.0,
            width=89.0,
            height=38.0,
            volume=3_382_000.0,
        )

        json_str = resource.model_dump_json()
        data = json.loads(json_str)

        assert data["id"] == "test-piece"
        assert data["type"] == "2x4"  # Enum serialized as string
        assert data["length"] == 1000.0


class TestResourceSummary:
    """Test ResourceSummary model."""

    def test_should_create_resource_summary(self):
        """Should create ResourceSummary with aggregated data."""
        pieces = [
            PieceResource(
                id="p1",
                type=PieceType.PT_2x4,
                length=1000.0,
                width=89.0,
                height=38.0,
                volume=3_382_000.0,
            ),
            PieceResource(
                id="p2",
                type=PieceType.PT_2x4,
                length=800.0,
                width=89.0,
                height=38.0,
                volume=2_705_600.0,
            ),
            PieceResource(
                id="p3",
                type=PieceType.PT_1x4,
                length=600.0,
                width=89.0,
                height=19.0,
                volume=1_014_600.0,
            ),
        ]

        summary = ResourceSummary(
            pieces=pieces,
            total_pieces=3,
            pieces_by_type={PieceType.PT_2x4: 2, PieceType.PT_1x4: 1},
            total_length_by_type={PieceType.PT_2x4: 1800.0, PieceType.PT_1x4: 600.0},
            total_volume=7_102_200.0,
        )

        assert summary.total_pieces == 3
        assert summary.pieces_by_type[PieceType.PT_2x4] == 2
        assert summary.pieces_by_type[PieceType.PT_1x4] == 1
        assert summary.total_length_by_type[PieceType.PT_2x4] == 1800.0
        assert summary.total_volume == 7_102_200.0

    def test_should_serialize_summary_to_json(self):
        """Should serialize ResourceSummary to JSON with proper type conversion."""
        summary = ResourceSummary(
            pieces=[],
            total_pieces=2,
            pieces_by_type={PieceType.PT_2x4: 2},
            total_length_by_type={PieceType.PT_2x4: 1800.0},
            total_volume=6_087_600.0,
        )

        json_str = summary.model_dump_json()
        data = json.loads(json_str)

        # Check that PieceType keys are serialized as strings
        assert "pieces_by_type" in data
        # Pydantic serializes enum dict keys to their values in JSON
        assert "2x4" in data["pieces_by_type"]
        assert data["pieces_by_type"]["2x4"] == 2

    def test_pretty_print_formatting(self):
        """Should generate human-readable summary."""
        summary = ResourceSummary(
            pieces=[],
            total_pieces=5,
            pieces_by_type={PieceType.PT_2x4: 3, PieceType.PT_1x4: 2},
            total_length_by_type={PieceType.PT_2x4: 3000.0, PieceType.PT_1x4: 1200.0},
            total_volume=12_000_000.0,
        )

        output = summary.pretty_print()

        assert "Total pieces: 5" in output
        assert "2x4: 3 pieces (total length: 3000.0mm)" in output
        assert "1x4: 2 pieces (total length: 1200.0mm)" in output
        assert "Total volume: 12,000,000.0 mm³" in output


class TestExtractResources:
    """Test extract_resources function."""

    def test_should_extract_from_simple_model(self):
        """Should extract resources from a model with two pieces."""
        # Create a simple model
        p1 = Piece.of(PieceType.PT_2x4, 1000.0, "piece-1")
        p2 = Piece.of(PieceType.PT_2x4, 800.0, "piece-2")

        # Connection doesn't affect resources, but include for completeness
        conn = Connection(
            lhs=Anchor(
                contact_face="front", edge_shared_face="top", offset=FromMax(value=100)
            ),
            rhs=Anchor(
                contact_face="bottom",
                edge_shared_face="front",
                offset=FromMin(value=50),
            ),
        )

        model = Model.of(
            pieces=[p1, p2], connections=[(PiecePair(base=p1, target=p2), conn)]
        )

        # Extract resources
        resources = extract_resources(model)

        # Verify results
        assert resources.total_pieces == 2
        assert resources.pieces_by_type[PieceType.PT_2x4] == 2
        assert resources.total_length_by_type[PieceType.PT_2x4] == 1800.0

        # Check individual pieces
        assert len(resources.pieces) == 2
        piece1 = next(p for p in resources.pieces if p.id == "piece-1")
        assert piece1.length == 1000.0
        assert piece1.width == 89.0
        assert piece1.height == 38.0
        assert piece1.volume == 89.0 * 38.0 * 1000.0

    def test_should_extract_from_mixed_type_model(self):
        """Should extract resources from model with different lumber types."""
        pieces = [
            Piece.of(PieceType.PT_2x4, 1000.0, "2x4-1"),
            Piece.of(PieceType.PT_2x4, 800.0, "2x4-2"),
            Piece.of(PieceType.PT_1x4, 600.0, "1x4-1"),
            Piece.of(PieceType.PT_1x4, 500.0, "1x4-2"),
            Piece.of(PieceType.PT_1x4, 400.0, "1x4-3"),
        ]

        model = Model.of(pieces=pieces, connections=[])
        resources = extract_resources(model)

        assert resources.total_pieces == 5
        assert resources.pieces_by_type[PieceType.PT_2x4] == 2
        assert resources.pieces_by_type[PieceType.PT_1x4] == 3
        assert resources.total_length_by_type[PieceType.PT_2x4] == 1800.0
        assert resources.total_length_by_type[PieceType.PT_1x4] == 1500.0

        # Verify volume calculation
        expected_volume_2x4 = 89.0 * 38.0 * 1800.0
        expected_volume_1x4 = 89.0 * 19.0 * 1500.0
        expected_total = expected_volume_2x4 + expected_volume_1x4

        assert resources.total_volume == pytest.approx(expected_total)

    def test_should_handle_empty_model(self):
        """Should handle model with no pieces."""
        model = Model.of(pieces=[], connections=[])
        resources = extract_resources(model)

        assert resources.total_pieces == 0
        assert len(resources.pieces) == 0
        assert resources.pieces_by_type == {}
        assert resources.total_length_by_type == {}
        assert resources.total_volume == 0.0

    def test_json_serialization_roundtrip(self):
        """Should serialize and deserialize resources to/from JSON."""
        # Create model
        pieces = [
            Piece.of(PieceType.PT_2x4, 1000.0, "p1"),
            Piece.of(PieceType.PT_1x4, 600.0, "p2"),
        ]
        model = Model.of(pieces=pieces, connections=[])

        # Extract resources
        resources = extract_resources(model)

        # Serialize to JSON
        json_str = resources.model_dump_json(indent=2)

        # Verify JSON contains expected data
        data = json.loads(json_str)
        assert data["total_pieces"] == 2
        assert len(data["pieces"]) == 2

        # Check that piece types are properly serialized
        piece_data = data["pieces"][0]
        assert piece_data["type"] == "2x4" or piece_data["type"] == "1x4"
