"""Tests for build123d converter."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from nichiyou_daiku.rendering.build123d_converter import GraphToBuild123D
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

        result = converter.lumber_to_box(piece, position=(100, 200, 300))

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

        result = converter.lumber_to_box(piece, rotation=(45, 0, 90))

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
