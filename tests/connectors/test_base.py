"""Tests for the JointConnector abstract base class."""

import pytest
from typing import List, Dict, Any

from nichiyou_daiku.connectors.base import (
    JointConnector,
    DrillPoint,
    AssemblyStep,
    Tool,
    ConnectorStrength,
    ValidationError,
)
from nichiyou_daiku.core.lumber import LumberPiece, LumberType, Face
from nichiyou_daiku.core.geometry import FaceLocation


class TestJointConnectorAbstract:
    """Test the JointConnector abstract base class."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that JointConnector cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            JointConnector()

    def test_connector_strength_enum(self):
        """Test ConnectorStrength enum has expected values."""
        assert hasattr(ConnectorStrength, "WEAK")
        assert hasattr(ConnectorStrength, "MEDIUM")
        assert hasattr(ConnectorStrength, "STRONG")
        assert hasattr(ConnectorStrength, "VERY_STRONG")

        # Check ordering
        assert ConnectorStrength.WEAK.value < ConnectorStrength.MEDIUM.value
        assert ConnectorStrength.MEDIUM.value < ConnectorStrength.STRONG.value
        assert ConnectorStrength.STRONG.value < ConnectorStrength.VERY_STRONG.value


class TestDrillPoint:
    """Test the DrillPoint dataclass."""

    def test_drill_point_creation(self):
        """Test creating a drill point."""
        face_loc = FaceLocation(Face.TOP, 0.5, 0.5)
        point = DrillPoint(
            piece_id="piece1", face_location=face_loc, diameter=8.0, depth=25.0
        )

        assert point.piece_id == "piece1"
        assert point.face_location == face_loc
        assert point.diameter == 8.0
        assert point.depth == 25.0

    def test_drill_point_immutable(self):
        """Test that drill point is immutable."""
        face_loc = FaceLocation(Face.TOP, 0.5, 0.5)
        point = DrillPoint("piece1", face_loc, 8.0, 25.0)

        with pytest.raises(AttributeError):
            point.diameter = 10.0


class TestTool:
    """Test the Tool dataclass."""

    def test_tool_creation(self):
        """Test creating a tool."""
        tool = Tool(
            name="Power Drill",
            type="drill",
            required_bits=["8mm wood bit", "3mm pilot bit"],
        )

        assert tool.name == "Power Drill"
        assert tool.type == "drill"
        assert len(tool.required_bits) == 2
        assert "8mm wood bit" in tool.required_bits

    def test_tool_with_optional_fields(self):
        """Test tool with optional specifications."""
        tool = Tool(
            name="Screwdriver",
            type="driver",
            specifications={"torque": "5-10 Nm", "tip": "Phillips #2"},
        )

        assert tool.specifications is not None
        assert tool.specifications["torque"] == "5-10 Nm"


class TestAssemblyStep:
    """Test the AssemblyStep dataclass."""

    def test_assembly_step_creation(self):
        """Test creating an assembly step."""
        step = AssemblyStep(
            order=1,
            description="Drill pilot holes in piece A",
            pieces_involved=["pieceA"],
            tools_required=["drill"],
        )

        assert step.order == 1
        assert "pilot holes" in step.description
        assert "pieceA" in step.pieces_involved
        assert "drill" in step.tools_required

    def test_assembly_step_with_warnings(self):
        """Test assembly step with warnings."""
        step = AssemblyStep(
            order=2,
            description="Attach pieces",
            pieces_involved=["pieceA", "pieceB"],
            tools_required=["screwdriver"],
            warnings=["Ensure pieces are aligned", "Do not overtighten"],
        )

        assert len(step.warnings) == 2
        assert "aligned" in step.warnings[0]


class MockConnector(JointConnector):
    """Mock implementation of JointConnector for testing."""

    def __init__(self, strength: ConnectorStrength = ConnectorStrength.MEDIUM):
        self._strength = strength
        self.validate_called = False
        self.calculate_called = False

    def validate_connection(
        self,
        piece1: LumberPiece,
        location1: FaceLocation,
        piece2: LumberPiece,
        location2: FaceLocation,
        **kwargs: Any,
    ) -> None:
        """Mock validation."""
        self.validate_called = True
        # Simulate validation failure for specific case
        if piece1.lumber_type != piece2.lumber_type:
            raise ValidationError("Lumber types must match for this connector")

    def calculate_drill_points(
        self,
        piece1: LumberPiece,
        location1: FaceLocation,
        piece2: LumberPiece,
        location2: FaceLocation,
        **kwargs: Any,
    ) -> List[DrillPoint]:
        """Mock drill point calculation."""
        self.calculate_called = True
        return [
            DrillPoint(piece1.id, location1, 8.0, 25.0),
            DrillPoint(piece2.id, location2, 8.0, 25.0),
        ]

    def get_required_tools(self) -> List[Tool]:
        """Mock tool requirements."""
        return [
            Tool("Power Drill", "drill", ["8mm bit"]),
            Tool("Screwdriver", "driver"),
        ]

    def get_assembly_steps(
        self,
        piece1: LumberPiece,
        location1: FaceLocation,
        piece2: LumberPiece,
        location2: FaceLocation,
        **kwargs: Any,
    ) -> List[AssemblyStep]:
        """Mock assembly steps."""
        return [
            AssemblyStep(
                1, f"Drill holes in {piece1.id}", [piece1.id], ["Power Drill"]
            ),
            AssemblyStep(
                2,
                f"Attach {piece1.id} to {piece2.id}",
                [piece1.id, piece2.id],
                ["Screwdriver"],
            ),
        ]

    @property
    def estimated_strength(self) -> ConnectorStrength:
        """Mock strength estimation."""
        return self._strength

    def get_connector_info(self) -> Dict[str, Any]:
        """Get information about this connector."""
        return {
            "type": "mock",
            "strength": self.estimated_strength.name,
            "tools_required": len(self.get_required_tools()),
        }


class TestMockConnectorImplementation:
    """Test the mock connector implementation."""

    def test_mock_connector_creation(self):
        """Test creating a mock connector."""
        connector = MockConnector()
        assert connector.estimated_strength == ConnectorStrength.MEDIUM

        strong_connector = MockConnector(ConnectorStrength.STRONG)
        assert strong_connector.estimated_strength == ConnectorStrength.STRONG

    def test_validate_connection_success(self):
        """Test successful connection validation."""
        connector = MockConnector()
        piece1 = LumberPiece("p1", LumberType.LUMBER_2X4, 1000)
        piece2 = LumberPiece("p2", LumberType.LUMBER_2X4, 1000)
        loc1 = FaceLocation(Face.TOP, 0.5, 0.5)
        loc2 = FaceLocation(Face.BOTTOM, 0.5, 0.5)

        # Should not raise
        connector.validate_connection(piece1, loc1, piece2, loc2)
        assert connector.validate_called

    def test_validate_connection_failure(self):
        """Test connection validation failure."""
        connector = MockConnector()
        piece1 = LumberPiece("p1", LumberType.LUMBER_2X4, 1000)
        piece2 = LumberPiece("p2", LumberType.LUMBER_1X4, 1000)
        loc1 = FaceLocation(Face.TOP, 0.5, 0.5)
        loc2 = FaceLocation(Face.BOTTOM, 0.5, 0.5)

        with pytest.raises(ValidationError, match="Lumber types must match"):
            connector.validate_connection(piece1, loc1, piece2, loc2)

    def test_calculate_drill_points(self):
        """Test drill point calculation."""
        connector = MockConnector()
        piece1 = LumberPiece("p1", LumberType.LUMBER_2X4, 1000)
        piece2 = LumberPiece("p2", LumberType.LUMBER_2X4, 1000)
        loc1 = FaceLocation(Face.TOP, 0.5, 0.5)
        loc2 = FaceLocation(Face.BOTTOM, 0.5, 0.5)

        points = connector.calculate_drill_points(piece1, loc1, piece2, loc2)

        assert len(points) == 2
        assert points[0].piece_id == "p1"
        assert points[1].piece_id == "p2"
        assert all(p.diameter == 8.0 for p in points)
        assert connector.calculate_called

    def test_get_required_tools(self):
        """Test getting required tools."""
        connector = MockConnector()
        tools = connector.get_required_tools()

        assert len(tools) == 2
        assert any(t.name == "Power Drill" for t in tools)
        assert any(t.name == "Screwdriver" for t in tools)

        drill = next(t for t in tools if t.type == "drill")
        assert "8mm bit" in drill.required_bits

    def test_get_assembly_steps(self):
        """Test getting assembly steps."""
        connector = MockConnector()
        piece1 = LumberPiece("board1", LumberType.LUMBER_2X4, 1000)
        piece2 = LumberPiece("board2", LumberType.LUMBER_2X4, 1000)
        loc1 = FaceLocation(Face.TOP, 0.5, 0.5)
        loc2 = FaceLocation(Face.BOTTOM, 0.5, 0.5)

        steps = connector.get_assembly_steps(piece1, loc1, piece2, loc2)

        assert len(steps) == 2
        assert steps[0].order < steps[1].order
        assert "board1" in steps[0].pieces_involved
        assert "board1" in steps[1].pieces_involved
        assert "board2" in steps[1].pieces_involved

    def test_get_connector_info(self):
        """Test getting connector information."""
        connector = MockConnector(ConnectorStrength.VERY_STRONG)
        info = connector.get_connector_info()

        assert info["type"] == "mock"
        assert info["strength"] == "VERY_STRONG"
        assert info["tools_required"] == 2


class TestConnectorIntegration:
    """Test connector integration scenarios."""

    def test_full_connection_workflow(self):
        """Test complete workflow of creating a connection."""
        # Create pieces
        piece1 = LumberPiece("leg1", LumberType.LUMBER_2X4, 800)
        piece2 = LumberPiece("rail1", LumberType.LUMBER_2X4, 600)

        # Define connection locations
        loc1 = FaceLocation(Face.TOP, 0.5, 0.5)
        loc2 = FaceLocation(Face.BOTTOM, 0.2, 0.5)

        # Create connector
        connector = MockConnector(ConnectorStrength.STRONG)

        # Validate connection
        connector.validate_connection(piece1, loc1, piece2, loc2)

        # Get drill points
        drill_points = connector.calculate_drill_points(piece1, loc1, piece2, loc2)
        assert len(drill_points) > 0

        # Get required tools
        tools = connector.get_required_tools()
        assert len(tools) > 0

        # Get assembly steps
        steps = connector.get_assembly_steps(piece1, loc1, piece2, loc2)
        assert len(steps) > 0

        # Verify strength
        assert connector.estimated_strength == ConnectorStrength.STRONG

    def test_multiple_connector_types(self):
        """Test that different connector types can coexist."""
        weak_connector = MockConnector(ConnectorStrength.WEAK)
        strong_connector = MockConnector(ConnectorStrength.VERY_STRONG)

        piece1 = LumberPiece("p1", LumberType.LUMBER_1X4, 500)
        piece2 = LumberPiece("p2", LumberType.LUMBER_1X4, 500)
        loc = FaceLocation(Face.TOP, 0.5, 0.5)

        # Both should work independently
        weak_points = weak_connector.calculate_drill_points(piece1, loc, piece2, loc)
        strong_points = strong_connector.calculate_drill_points(
            piece1, loc, piece2, loc
        )

        assert len(weak_points) == len(strong_points)  # Same mock implementation
        assert weak_connector.estimated_strength < strong_connector.estimated_strength
