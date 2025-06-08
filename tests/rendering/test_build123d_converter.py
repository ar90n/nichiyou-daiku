"""Tests for build123d converter."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from nichiyou_daiku.rendering.build123d_converter import (
    GraphToBuild123D,
    lumber_to_box,
    graph_to_assembly,
)
from nichiyou_daiku.graph.woodworking_graph import WoodworkingGraph
from nichiyou_daiku.core.lumber import LumberPiece, LumberType


class TestGraphToBuild123D:
    """Test the GraphToBuild123D converter."""

    def test_init(self):
        """Test initialization."""
        converter = GraphToBuild123D()
        assert converter is not None

    @patch("nichiyou_daiku.rendering.build123d_converter.Box")
    def test_lumber_to_box_dimensions(self, mock_box_class):
        """Test lumber_to_box creates Box with correct dimensions."""
        # Setup mock
        mock_box = MagicMock()
        mock_box.located.return_value = mock_box
        mock_box_class.return_value = mock_box

        converter = GraphToBuild123D()
        piece = LumberPiece("test", LumberType.LUMBER_2X4, 1000)

        result = converter.lumber_to_box(piece)

        # Verify Box was created with correct dimensions (length, width, height)
        mock_box_class.assert_called_once_with(1000, 38, 89)
        assert result == mock_box

    @patch("nichiyou_daiku.rendering.build123d_converter.Box")
    @patch("nichiyou_daiku.rendering.build123d_converter.Location")
    def test_lumber_to_box_with_position(self, mock_location_class, mock_box_class):
        """Test lumber_to_box applies position correctly."""
        # Setup mocks
        mock_box = MagicMock()
        mock_location = MagicMock()
        mock_box_class.return_value = mock_box
        mock_location_class.return_value = mock_location

        converter = GraphToBuild123D()
        piece = LumberPiece("test", LumberType.LUMBER_1X4, 500)

        converter.lumber_to_box(piece, position=(100, 200, 300))

        # Verify position was applied
        mock_location_class.assert_called_once_with((100, 200, 300))
        mock_box.located.assert_called_once_with(mock_location)

    @patch("nichiyou_daiku.rendering.build123d_converter.Box")
    @patch("nichiyou_daiku.rendering.build123d_converter.Location")
    def test_lumber_to_box_with_rotation(self, mock_location_class, mock_box_class):
        """Test lumber_to_box applies rotation correctly."""
        # Setup mocks
        mock_box = MagicMock()
        mock_location = MagicMock()
        mock_location.__mul__ = MagicMock(return_value=mock_location)
        mock_box_class.return_value = mock_box
        mock_location_class.return_value = mock_location

        converter = GraphToBuild123D()
        piece = LumberPiece("test", LumberType.LUMBER_2X8, 800)

        converter.lumber_to_box(piece, rotation=(45, 0, 90))

        # Verify rotations were applied
        assert mock_location.__mul__.call_count == 2  # X and Z rotations
        mock_box.located.assert_called_once()

    def test_graph_to_compound_empty_graph_no_mock(self):
        """Test graph_to_compound with empty graph returns None."""
        converter = GraphToBuild123D()
        graph = WoodworkingGraph()

        result = converter.graph_to_compound(graph)
        assert result is None

    @patch("nichiyou_daiku.rendering.build123d_converter.Compound")
    def test_graph_to_compound_empty_graph(self, mock_compound_class):
        """Test graph_to_compound with empty graph."""
        converter = GraphToBuild123D()
        graph = WoodworkingGraph()

        result = converter.graph_to_compound(graph)

        # Should return None for empty graph
        assert result is None
        mock_compound_class.assert_not_called()

    @patch("nichiyou_daiku.rendering.build123d_converter.Box")
    @patch("nichiyou_daiku.rendering.build123d_converter.Compound")
    def test_graph_to_compound_single_piece(self, mock_compound_class, mock_box_class):
        """Test graph_to_compound with single piece."""
        # Setup mocks
        mock_box = MagicMock()
        mock_box.located.return_value = mock_box
        mock_box_class.return_value = mock_box
        mock_compound = MagicMock()
        mock_compound_class.return_value = mock_compound

        converter = GraphToBuild123D()
        graph = WoodworkingGraph()

        # Add a piece to the graph
        piece = LumberPiece("test", LumberType.LUMBER_2X4, 1000)
        graph.add_lumber_piece(piece)

        result = converter.graph_to_compound(graph)

        # Verify compound was created with the box
        mock_compound_class.assert_called_once()
        assert result == mock_compound

    @patch("nichiyou_daiku.rendering.build123d_converter.Box")
    @patch("nichiyou_daiku.rendering.build123d_converter.Compound")
    def test_graph_to_compound_multiple_pieces(
        self, mock_compound_class, mock_box_class
    ):
        """Test graph_to_compound with multiple pieces."""
        # Setup mocks
        mock_box = MagicMock()
        mock_box.located.return_value = mock_box
        mock_box_class.return_value = mock_box
        mock_compound = MagicMock()
        mock_compound_class.return_value = mock_compound

        converter = GraphToBuild123D()
        graph = WoodworkingGraph()

        # Add multiple pieces
        pieces = [
            LumberPiece("p1", LumberType.LUMBER_2X4, 1000),
            LumberPiece("p2", LumberType.LUMBER_2X8, 1500),
            LumberPiece("p3", LumberType.LUMBER_1X4, 800),
        ]
        for piece in pieces:
            graph.add_lumber_piece(piece)

        result = converter.graph_to_compound(graph)

        # Verify Box was created for each piece
        assert mock_box_class.call_count == 3
        # Verify compound was created
        mock_compound_class.assert_called_once()
        assert result == mock_compound

    def test_convert_method_alias(self):
        """Test that convert() is an alias for graph_to_compound()."""
        converter = GraphToBuild123D()
        graph = WoodworkingGraph()

        # Mock graph_to_compound
        converter.graph_to_compound = Mock(return_value="test_result")

        result = converter.convert(graph)

        converter.graph_to_compound.assert_called_once_with(graph)
        assert result == "test_result"


class TestStandaloneFunctions:
    """Test the standalone conversion functions for Task 4.2 and 4.3."""

    @patch("nichiyou_daiku.rendering.build123d_converter.Box")
    def test_lumber_to_box_basic(self, mock_box_class):
        """Test standalone lumber_to_box with basic usage."""
        # Setup mock
        mock_box = MagicMock()
        mock_box_class.return_value = mock_box

        # Test with 2x4
        piece = LumberPiece("test", LumberType.LUMBER_2X4, 1000)
        result = lumber_to_box(piece)

        # Verify Box was created with correct dimensions
        mock_box_class.assert_called_once_with(1000, 38, 89)
        assert result == mock_box

    @patch("nichiyou_daiku.rendering.build123d_converter.Box")
    def test_lumber_to_box_all_lumber_types(self, mock_box_class):
        """Test lumber_to_box with all lumber types."""
        test_cases = [
            (LumberType.LUMBER_1X4, 1000, (1000, 19, 89)),
            (LumberType.LUMBER_1X8, 1000, (1000, 19, 184)),
            (LumberType.LUMBER_1X16, 1000, (1000, 19, 286)),
            (LumberType.LUMBER_2X4, 1000, (1000, 38, 89)),
            (LumberType.LUMBER_2X8, 1000, (1000, 38, 184)),
            (LumberType.LUMBER_2X16, 1000, (1000, 38, 286)),
        ]

        for lumber_type, length, expected_dims in test_cases:
            mock_box_class.reset_mock()
            piece = LumberPiece(f"test_{lumber_type.value}", lumber_type, length)
            lumber_to_box(piece)
            mock_box_class.assert_called_once_with(*expected_dims)

    @patch("nichiyou_daiku.rendering.build123d_converter.Box")
    def test_lumber_to_box_edge_cases(self, mock_box_class):
        """Test lumber_to_box with edge cases."""
        # Zero length
        piece = LumberPiece("zero", LumberType.LUMBER_2X4, 0)
        lumber_to_box(piece)
        mock_box_class.assert_called_with(0, 38, 89)

        # Very small length
        mock_box_class.reset_mock()
        piece = LumberPiece("tiny", LumberType.LUMBER_2X4, 0.001)
        lumber_to_box(piece)
        mock_box_class.assert_called_with(0.001, 38, 89)

        # Very large length
        mock_box_class.reset_mock()
        piece = LumberPiece("huge", LumberType.LUMBER_2X4, 10000)
        lumber_to_box(piece)
        mock_box_class.assert_called_with(10000, 38, 89)

    @patch("nichiyou_daiku.rendering.build123d_converter.lumber_to_box")
    @patch("nichiyou_daiku.rendering.build123d_converter.Compound")
    def test_graph_to_assembly_basic(self, mock_compound_class, mock_lumber_to_box):
        """Test standalone graph_to_assembly function."""
        # Setup mocks
        mock_box = MagicMock()
        mock_lumber_to_box.return_value = mock_box
        mock_compound = MagicMock()
        mock_compound_class.return_value = mock_compound

        # Create graph with pieces
        graph = WoodworkingGraph()
        pieces = [
            LumberPiece("p1", LumberType.LUMBER_2X4, 1000),
            LumberPiece("p2", LumberType.LUMBER_2X8, 1500),
        ]
        for piece in pieces:
            graph.add_lumber_piece(piece)

        # Call function
        result = graph_to_assembly(graph)

        # Verify
        assert mock_lumber_to_box.call_count == 2
        mock_compound_class.assert_called_once()
        assert result == mock_compound

    def test_graph_to_assembly_empty_graph(self):
        """Test graph_to_assembly with empty graph."""
        graph = WoodworkingGraph()
        result = graph_to_assembly(graph)
        assert result is None

    @patch("nichiyou_daiku.rendering.build123d_converter.lumber_to_box")
    def test_graph_to_assembly_error_handling(self, mock_lumber_to_box):
        """Test graph_to_assembly error handling."""
        # Setup mock to raise exception
        mock_lumber_to_box.side_effect = Exception("Test error")

        graph = WoodworkingGraph()
        graph.add_lumber_piece(LumberPiece("test", LumberType.LUMBER_2X4, 1000))

        # Should propagate the exception
        with pytest.raises(Exception, match="Test error"):
            graph_to_assembly(graph)
