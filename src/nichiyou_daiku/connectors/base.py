"""Abstract base class for joint connectors.

This module defines the interface that all connector implementations must follow,
ensuring consistent behavior across different joining methods.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Dict, List, Optional

from nichiyou_daiku.core.geometry import FaceLocation
from nichiyou_daiku.core.lumber import LumberPiece


class ConnectorStrength(IntEnum):
    """Strength rating for connectors.

    >>> ConnectorStrength.WEAK < ConnectorStrength.MEDIUM
    True
    >>> ConnectorStrength.STRONG.value
    3
    """

    WEAK = 1
    MEDIUM = 2
    STRONG = 3
    VERY_STRONG = 4


class ValidationError(Exception):
    """Raised when connector validation fails."""

    pass


@dataclass(frozen=True)
class DrillPoint:
    """Represents a point where drilling is required.

    Attributes:
        piece_id: ID of the lumber piece to drill
        face_location: Location on the face where to drill
        diameter: Drill bit diameter in millimeters
        depth: Drilling depth in millimeters

    >>> from nichiyou_daiku.core.lumber import Face
    >>> loc = FaceLocation(Face.TOP, 0.5, 0.5)
    >>> drill = DrillPoint("piece1", loc, 8.0, 25.0)
    >>> drill.diameter
    8.0
    """

    piece_id: str
    face_location: FaceLocation
    diameter: float
    depth: float


@dataclass(frozen=True)
class Tool:
    """Represents a tool required for assembly.

    Attributes:
        name: Human-readable tool name
        type: Tool category (drill, driver, saw, etc.)
        required_bits: Optional list of specific bits/attachments
        specifications: Optional additional specifications
    """

    name: str
    type: str
    required_bits: Optional[List[str]] = None
    specifications: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class AssemblyStep:
    """Represents a single step in the assembly process.

    Attributes:
        order: Step number (1-based)
        description: Human-readable instruction
        pieces_involved: List of piece IDs involved in this step
        tools_required: List of tool names needed
        warnings: Optional safety warnings or important notes
    """

    order: int
    description: str
    pieces_involved: List[str]
    tools_required: List[str]
    warnings: Optional[List[str]] = None


class JointConnector(ABC):
    """Abstract base class for all joint connectors.

    This class defines the interface that all concrete connector implementations
    must follow. It ensures consistent behavior for validation, drill point
    calculation, tool requirements, and assembly instructions.
    """

    @abstractmethod
    def validate_connection(
        self,
        piece1: LumberPiece,
        location1: FaceLocation,
        piece2: LumberPiece,
        location2: FaceLocation,
        **kwargs: Any,
    ) -> None:
        """Validate that this connector can join the given pieces at specified locations.

        Args:
            piece1: First lumber piece
            location1: Connection location on first piece
            piece2: Second lumber piece
            location2: Connection location on second piece
            **kwargs: Connector-specific parameters

        Raises:
            ValidationError: If the connection is not valid

        Note:
            Implementations should check:
            - Lumber dimensions compatibility
            - Face orientations
            - Material thickness requirements
            - Any connector-specific constraints
        """
        pass

    @abstractmethod
    def calculate_drill_points(
        self,
        piece1: LumberPiece,
        location1: FaceLocation,
        piece2: LumberPiece,
        location2: FaceLocation,
        **kwargs: Any,
    ) -> List[DrillPoint]:
        """Calculate drilling locations for this connection.

        Args:
            piece1: First lumber piece
            location1: Connection location on first piece
            piece2: Second lumber piece
            location2: Connection location on second piece
            **kwargs: Connector-specific parameters (e.g., screw_count)

        Returns:
            List of drill points with locations and specifications

        Note:
            The returned drill points should be in the local coordinate
            system of each piece. Graph traversal will handle world
            coordinate transformation.
        """
        pass

    @abstractmethod
    def get_required_tools(self) -> List[Tool]:
        """Get list of tools required for this connector type.

        Returns:
            List of tools with specifications

        Note:
            This should return all tools that might be needed,
            including drill bits, drivers, measuring tools, etc.
        """
        pass

    @abstractmethod
    def get_assembly_steps(
        self,
        piece1: LumberPiece,
        location1: FaceLocation,
        piece2: LumberPiece,
        location2: FaceLocation,
        **kwargs: Any,
    ) -> List[AssemblyStep]:
        """Generate step-by-step assembly instructions.

        Args:
            piece1: First lumber piece
            location1: Connection location on first piece
            piece2: Second lumber piece
            location2: Connection location on second piece
            **kwargs: Connector-specific parameters

        Returns:
            Ordered list of assembly steps

        Note:
            Steps should be clear, actionable instructions that
            a DIY enthusiast can follow. Include safety warnings
            where appropriate.
        """
        pass

    @property
    @abstractmethod
    def estimated_strength(self) -> ConnectorStrength:
        """Get the estimated strength rating for this connector type.

        Returns:
            Strength rating enum value

        Note:
            This is a general rating. Actual strength depends on
            implementation quality, wood type, and load direction.
        """
        pass

    def get_connector_info(self) -> Dict[str, Any]:
        """Get general information about this connector.

        Returns:
            Dictionary with connector metadata

        Note:
            Subclasses can override this to provide additional
            connector-specific information.
        """
        return {
            "type": self.__class__.__name__,
            "strength": self.estimated_strength.name,
            "tools_required": len(self.get_required_tools()),
        }
