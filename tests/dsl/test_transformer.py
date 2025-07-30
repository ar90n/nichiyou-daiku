"""Tests for the DSL transformer."""

import pytest
from lark import Token

from nichiyou_daiku.core.geometry.offset import FromMax, FromMin
from nichiyou_daiku.core.piece import PieceType
from nichiyou_daiku.core.connection import Anchor
from nichiyou_daiku.dsl.exceptions import DSLSemanticError, DSLValidationError
from nichiyou_daiku.dsl.transformer import DSLTransformer


class TestTransformerPieceHandling:
    """Test transformer piece handling."""

    def test_transform_piece_props(self):
        """Test piece properties transformation."""
        transformer = DSLTransformer()

        # Test with properties
        props = {"length": 1000.0, "note": "test"}
        result = transformer.piece_props([props])
        assert result == props

        # Test empty properties
        result = transformer.piece_props([])
        assert result == {}

    def test_piece_id_handling(self):
        """Test that piece IDs are handled correctly."""
        transformer = DSLTransformer()

        # Simulate piece definition with ID
        transformer.piece_def(
            [Token("CNAME", "beam1"), Token("PIECE_TYPE", "2x4"), {"length": 1000.0}]
        )

        assert "beam1" in transformer.pieces
        piece = transformer.pieces["beam1"]
        assert piece.id == "beam1"
        assert piece.type == PieceType.PT_2x4
        assert piece.length == 1000.0

    def test_auto_generated_piece_id(self):
        """Test auto-generated piece IDs."""
        transformer = DSLTransformer()

        # Simulate piece definition without ID
        transformer.piece_def([Token("PIECE_TYPE", "2x4"), {"length": 1000.0}])

        # Should have one piece with auto-generated ID
        assert len(transformer.pieces) == 1
        piece = list(transformer.pieces.values())[0]
        assert len(piece.id) == 36  # UUID length
        assert piece.type == PieceType.PT_2x4
        assert piece.length == 1000.0


class TestTransformerOffsetHandling:
    """Test transformer offset handling."""

    def test_transform_offset_values(self):
        """Test offset value transformation."""
        transformer = DSLTransformer()

        # Test FromMin
        items = [Token("FROM_MIN", "FromMin"), Token("NUMBER", "100")]
        result = transformer.offset_value(items)
        assert isinstance(result, FromMin)
        assert result.value == 100.0

        # Test FromMax
        items = [Token("FROM_MAX", "FromMax"), Token("NUMBER", "200.5")]
        result = transformer.offset_value(items)
        assert isinstance(result, FromMax)
        assert result.value == 200.5

    def test_invalid_offset_type(self):
        """Test invalid offset type."""
        transformer = DSLTransformer()

        items = [Token("CNAME", "FromInvalid"), Token("NUMBER", "100")]
        with pytest.raises(DSLValidationError) as exc_info:
            transformer.offset_value(items)
        assert "Invalid offset type" in str(exc_info.value)


class TestTransformerValueHandling:
    """Test transformer value handling."""

    def test_transform_string_value(self):
        """Test string value transformation."""
        transformer = DSLTransformer()

        token = Token("ESCAPED_STRING", '"test string"')
        result = transformer.value([token])
        assert result == "test string"

        # Test with escaped quotes
        token = Token("ESCAPED_STRING", '"test \\"quoted\\" string"')
        result = transformer.value([token])
        assert result == 'test "quoted" string'

    def test_transform_number_value(self):
        """Test number value transformation."""
        transformer = DSLTransformer()

        token = Token("NUMBER", "123.45")
        result = transformer.value([token])
        assert result == 123.45

        token = Token("NUMBER", "-42")
        result = transformer.value([token])
        assert result == -42.0

    def test_transform_offset_as_value(self):
        """Test offset as value transformation."""
        transformer = DSLTransformer()

        offset = FromMax(value=100.0)
        result = transformer.value([offset])
        assert result is offset


class TestTransformerConnectionHandling:
    """Test transformer connection handling."""

    def test_anchor_creation(self):
        """Test anchor creation from properties."""
        transformer = DSLTransformer()

        props = {
            "contact_face": "front",
            "edge_shared_face": "top",
            "offset": FromMax(value=100.0),
        }

        anchor = transformer._create_anchor(props)
        assert anchor.contact_face == "front"
        assert anchor.edge_shared_face == "top"
        assert isinstance(anchor.offset, FromMax)
        assert anchor.offset.value == 100.0

    def test_anchor_missing_properties(self):
        """Test anchor creation with missing properties."""
        transformer = DSLTransformer()

        # Missing contact_face
        props = {"edge_shared_face": "top", "offset": FromMax(value=100.0)}
        with pytest.raises(DSLValidationError) as exc_info:
            transformer._create_anchor(props)
        assert "contact_face" in str(exc_info.value)

        # Missing offset
        props = {"contact_face": "front", "edge_shared_face": "top"}
        with pytest.raises(DSLValidationError) as exc_info:
            transformer._create_anchor(props)
        assert "offset" in str(exc_info.value)


class TestCompactNotationTransformer:
    """Test compact notation transformation."""

    def test_compact_offset_transformation(self):
        """Test compact offset notation transformation."""
        transformer = DSLTransformer()

        # Test FromMin
        min_token = Token("COMPACT_FROM_MIN", "<")
        num_token = Token("NUMBER", "100")
        offset = transformer.compact_offset([min_token, num_token])
        assert isinstance(offset, FromMin)
        assert offset.value == 100.0

        # Test FromMax
        max_token = Token("COMPACT_FROM_MAX", ">")
        num_token = Token("NUMBER", "50.5")
        offset = transformer.compact_offset([max_token, num_token])
        assert isinstance(offset, FromMax)
        assert offset.value == 50.5

    def test_compact_anchor_props_transformation(self):
        """Test compact anchor properties transformation."""
        transformer = DSLTransformer()

        # Create test tokens
        contact_face = Token("COMPACT_FACE", "T")
        edge_face = Token("COMPACT_FACE", "F")
        offset = FromMin(value=0.0)

        anchor = transformer.compact_anchor_props([contact_face, edge_face, offset])

        assert isinstance(anchor, Anchor)
        assert anchor.contact_face == "top"
        assert anchor.edge_shared_face == "front"
        assert anchor.offset.value == 0.0

    def test_all_face_mappings(self):
        """Test all compact face notation mappings."""
        transformer = DSLTransformer()

        face_tests = [
            ("T", "top"),
            ("D", "bottom"),
            ("L", "left"),
            ("R", "right"),
            ("F", "front"),
            ("B", "back"),
        ]

        for compact, full in face_tests:
            token = Token("COMPACT_FACE", compact)
            offset = FromMin(value=0.0)
            anchor = transformer.compact_anchor_props([token, token, offset])
            assert anchor.contact_face == full
            assert anchor.edge_shared_face == full

    def test_invalid_compact_face_error(self):
        """Test error on invalid compact face notation."""
        transformer = DSLTransformer()

        # Invalid face character
        invalid_face = Token("COMPACT_FACE", "X")
        valid_face = Token("COMPACT_FACE", "T")
        offset = FromMin(value=0.0)

        with pytest.raises(DSLValidationError) as exc_info:
            transformer.compact_anchor_props([invalid_face, valid_face, offset])
        assert "Invalid compact face notation: X" in str(exc_info.value)

    def test_invalid_compact_offset_type(self):
        """Test error on invalid compact offset type."""
        transformer = DSLTransformer()

        # Invalid offset type token
        invalid_token = Token("INVALID", "?")
        num_token = Token("NUMBER", "100")

        with pytest.raises(DSLValidationError) as exc_info:
            transformer.compact_offset([invalid_token, num_token])
        assert "Invalid compact offset type" in str(exc_info.value)

    def test_compact_anchor_wrong_component_count(self):
        """Test error when compact anchor has wrong number of components."""
        transformer = DSLTransformer()

        # Too few components
        with pytest.raises(DSLValidationError) as exc_info:
            transformer.compact_anchor_props([Token("COMPACT_FACE", "T")])
        assert "3 components" in str(exc_info.value)

        # Too many components
        offset = FromMin(value=0.0)
        with pytest.raises(DSLValidationError) as exc_info:
            transformer.compact_anchor_props(
                [
                    Token("COMPACT_FACE", "T"),
                    Token("COMPACT_FACE", "F"),
                    offset,
                    Token("EXTRA", "X"),
                ]
            )
        assert "3 components" in str(exc_info.value)


class TestCompactPieceTransformer:
    """Test transformer handling of compact piece notation."""

    def test_compact_length_transformation(self):
        """Test transformation of compact length notation."""
        from lark import Token

        transformer = DSLTransformer()

        # Test compact_length method
        result = transformer.compact_length([Token("NUMBER", "1500")])
        assert result == 1500.0

        # Test with decimal
        result = transformer.compact_length([Token("NUMBER", "1500.75")])
        assert result == 1500.75

    def test_piece_def_with_compact_length(self):
        """Test piece definition transformation with compact length."""
        from lark import Token

        transformer = DSLTransformer()

        # Simulate piece_def with compact length
        items = [
            Token("CNAME", "beam1"),
            Token("PIECE_TYPE", "2x4"),
            1500.0,  # Direct length value from compact_length
        ]

        transformer.piece_def(items)

        assert "beam1" in transformer.pieces
        piece = transformer.pieces["beam1"]
        assert piece.type == PieceType.PT_2x4
        assert piece.length == 1500.0

    def test_piece_def_mixed_format(self):
        """Test that both JSON and compact formats work."""
        from lark import Token

        transformer = DSLTransformer()

        # First piece with compact notation
        transformer.piece_def(
            [Token("CNAME", "beam1"), Token("PIECE_TYPE", "2x4"), 1000.0]
        )

        # Second piece with JSON notation
        transformer.piece_def(
            [Token("CNAME", "beam2"), Token("PIECE_TYPE", "2x4"), {"length": 2000}]
        )

        assert len(transformer.pieces) == 2
        assert transformer.pieces["beam1"].length == 1000.0
        assert transformer.pieces["beam2"].length == 2000.0


class TestTransformerModelGeneration:
    """Test transformer model generation."""

    def test_empty_model_error(self):
        """Test that empty model raises error."""
        transformer = DSLTransformer()

        with pytest.raises(DSLSemanticError) as exc_info:
            transformer.start([])
        assert "No pieces defined" in str(exc_info.value)

    def test_model_generation(self):
        """Test complete model generation."""
        transformer = DSLTransformer()

        # Add pieces
        from nichiyou_daiku.core.piece import Piece

        transformer.pieces["beam1"] = Piece.of(PieceType.PT_2x4, 1000.0, "beam1")
        transformer.pieces["beam2"] = Piece.of(PieceType.PT_2x4, 1000.0, "beam2")

        # Generate model
        model = transformer.start([])

        assert len(model.pieces) == 2
        assert len(model.connections) == 0

        # Check pieces are in model (model.pieces is a dict)
        assert "beam1" in model.pieces
        assert "beam2" in model.pieces
