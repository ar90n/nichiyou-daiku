"""AST transformer for converting Lark parse trees to nichiyou-daiku models."""

from dataclasses import dataclass, field
from typing import Any, TypeVar, cast

from lark import Token, Transformer

from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.connection import (
    Connection,
    ConnectionType,
    DowelConnection,
    ScrewConnection,
    VanillaConnection,
)
from nichiyou_daiku.core.geometry.face import Face
from nichiyou_daiku.core.geometry.offset import FromMax, FromMin, Offset
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.screw import find_preset as find_screw_preset
from nichiyou_daiku.core.dowel import find_preset as find_dowel_preset
from nichiyou_daiku.dsl.exceptions import DSLSemanticError, DSLValidationError

# Type variable for connection types
T = TypeVar("T", DowelConnection, ScrewConnection)


@dataclass
class PieceComponents:
    """Components parsed from a piece definition."""

    piece_id: str | None = None
    piece_type: PieceType | None = None
    props: dict[str, Any] = field(default_factory=dict)
    length_value: float | None = None


@dataclass
class ConnectionComponents:
    """Components parsed from a connection definition."""

    piece_refs: list[str] = field(default_factory=list)
    anchor_props_list: list[dict] = field(default_factory=list)
    compact_anchor_list: list[Anchor] = field(default_factory=list)
    connection_type: ConnectionType | None = None


class DSLTransformer(Transformer):
    """Transform Lark parse trees into nichiyou-daiku models."""

    # Face mapping for compact notation
    FACE_MAPPING = {
        "T": "top",
        "D": "down",
        "L": "left",
        "R": "right",
        "F": "front",
        "B": "back",
    }

    def __init__(self):
        super().__init__()
        self.pieces: dict[str, Piece] = {}
        self.connections: list[Connection] = []

    # =========================================================================
    # Helper methods for reducing code duplication
    # =========================================================================

    def _extract_numbers(self, items: list[Any], count: int = 2) -> list[float]:
        """Extract numeric values from transformer items.

        Args:
            items: List of items from transformer
            count: Expected number of numeric values

        Returns:
            List of float values

        Raises:
            DSLValidationError: If the number of values doesn't match count
        """
        numbers = [
            float(item)
            for item in items
            if isinstance(item, Token) and item.type == "NUMBER"
        ]
        if len(numbers) != count:
            raise DSLValidationError(f"Expected {count} numbers, got {len(numbers)}")
        return numbers

    def _extract_connection_type(
        self, items: list[Any], conn_type: type[T], type_name: str
    ) -> T:
        """Extract a connection type from items.

        Args:
            items: List of items from transformer
            conn_type: The connection type class to look for
            type_name: Human-readable name for error messages

        Returns:
            The matching connection type instance

        Raises:
            DSLValidationError: If no matching connection type is found
        """
        for item in items:
            if isinstance(item, conn_type):
                return item
        raise DSLValidationError(f"Invalid {type_name} format: {items}")

    def _is_token_type(self, item: Any, token_type: str) -> bool:
        """Check if an item is a Token of a specific type.

        Args:
            item: The item to check
            token_type: The expected token type

        Returns:
            True if item is a Token of the specified type
        """
        return isinstance(item, Token) and item.type == token_type

    # =========================================================================
    # Entry points
    # =========================================================================

    def start(self, items: list[Any]) -> Model:
        """Transform the start rule into a Model."""
        if not self.pieces:
            raise DSLSemanticError("No pieces defined in the DSL")

        return Model.of(
            pieces=list(self.pieces.values()),
            connections=self.connections,
        )

    def statement(self, items: list[Any]) -> Any:
        """Pass through statement results."""
        return items[0]

    def piece_def(self, items: list[Any]) -> None:
        """Transform a piece definition."""
        components = self._parse_piece_components(items)
        piece = self._create_piece_from_components(components)
        self._register_piece(piece)

    def _parse_piece_components(self, items: list[Any]) -> PieceComponents:
        """Parse items into piece components."""
        components = PieceComponents()

        for item in items:
            if not isinstance(item, (Token, dict, float, int)):
                continue

            if isinstance(item, dict):
                components.props = item
            elif isinstance(item, (float, int)):
                components.length_value = float(item)
            elif isinstance(item, Token):
                match item.type:
                    case "CNAME":
                        components.piece_id = str(item)
                    case "PIECE_TYPE":
                        components.piece_type = self._parse_piece_type(item)

        return components

    def _parse_piece_type(self, token: Token) -> PieceType:
        """Parse a piece type token."""
        try:
            return PieceType.of(str(token))
        except ValueError:
            raise DSLValidationError(f"Invalid piece type: {token}")

    def _create_piece_from_components(self, components: PieceComponents) -> Piece:
        """Create a Piece from parsed components."""
        # Early return for missing piece type
        if components.piece_type is None:
            raise DSLSemanticError("Piece type is required")

        length = self._extract_length(components)
        return Piece.of(components.piece_type, length, components.piece_id)

    def _extract_length(self, components: PieceComponents) -> float:
        """Extract length from components."""
        # Compact notation length takes precedence
        if components.length_value is not None:
            return components.length_value

        # Extract from props
        if "length" not in components.props:
            raise DSLValidationError("Piece must have a 'length' property")

        try:
            return float(components.props["length"])
        except (TypeError, ValueError):
            raise DSLValidationError(
                f"Invalid length value: {components.props['length']}"
            )

    def _register_piece(self, piece: Piece) -> None:
        """Register a piece, checking for duplicates."""
        if piece.id in self.pieces:
            raise DSLSemanticError(f"Duplicate piece ID: {piece.id}")
        self.pieces[piece.id] = piece

    def piece_props(self, items: list[Any]) -> dict[str, Any]:
        """Transform piece properties into a dictionary."""
        if not items:
            return {}
        return items[0] if items else {}

    def prop_list(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Combine multiple properties into a single dictionary."""
        result = {}
        for prop in items:
            result.update(prop)
        return result

    def prop(self, items: list[Any]) -> dict[str, Any]:
        """Transform a single property."""
        key = self._unescape_string(items[0])
        value = items[1]
        return {key: value}

    def compact_length(self, items: list[Any]) -> float:
        """Transform compact length notation (=NUMBER)."""
        # items[0] should be the NUMBER token
        return float(items[0])

    def connection_def(self, items: list[Any]) -> None:
        """Transform a connection definition."""
        components = self._parse_connection_components(items)
        self._validate_connection_components(components)

        anchors = self._create_anchors_from_components(components)
        piece_ids = self._validate_piece_references(components.piece_refs)

        self._register_connection(piece_ids, anchors, components.connection_type)

    def _parse_connection_components(self, items: list[Any]) -> ConnectionComponents:
        """Parse items into connection components."""
        components = ConnectionComponents()

        def process_item(item: Any) -> None:
            """Process a single item, recursively handling lists."""
            if isinstance(item, list):
                for sub_item in item:
                    process_item(sub_item)
            elif isinstance(item, str):
                components.piece_refs.append(item)
            elif isinstance(item, dict):
                components.anchor_props_list.append(item)
            elif isinstance(item, Anchor):
                components.compact_anchor_list.append(item)
            elif isinstance(
                item, (VanillaConnection, DowelConnection, ScrewConnection)
            ):
                components.connection_type = item

        for item in items:
            process_item(item)

        return components

    def _validate_connection_components(self, components: ConnectionComponents) -> None:
        """Validate connection components."""
        # Early return for piece reference validation
        if len(components.piece_refs) != 2:
            raise DSLSemanticError("Connection must have exactly two piece references")

        # Check format mixing
        has_json = bool(components.anchor_props_list)
        has_compact = bool(components.compact_anchor_list)

        if has_json and has_compact:
            raise DSLSemanticError(
                "Connection must use either JSON format or compact format, not both"
            )

        if has_json and len(components.anchor_props_list) != 2:
            raise DSLSemanticError(
                "Connection must have exactly two anchor property sets"
            )

        if has_compact and len(components.compact_anchor_list) != 2:
            raise DSLSemanticError(
                "Connection must have exactly two compact anchor definitions"
            )

        if not has_json and not has_compact:
            raise DSLSemanticError("Connection must have anchor definitions")

    def _create_anchors_from_components(
        self, components: ConnectionComponents
    ) -> tuple[Anchor, Anchor]:
        """Create anchors from components."""
        if components.anchor_props_list:
            return (
                self._create_anchor(components.anchor_props_list[0]),
                self._create_anchor(components.anchor_props_list[1]),
            )

        # Compact format
        return (components.compact_anchor_list[0], components.compact_anchor_list[1])

    def _validate_piece_references(self, piece_refs: list[str]) -> tuple[str, str]:
        """Validate piece references exist and return their IDs."""
        base_id, target_id = piece_refs

        if base_id not in self.pieces:
            raise DSLSemanticError(f"Unknown piece reference: {base_id}")

        if target_id not in self.pieces:
            raise DSLSemanticError(f"Unknown piece reference: {target_id}")

        return base_id, target_id

    def _register_connection(
        self,
        piece_ids: tuple[str, str],
        anchors: tuple[Anchor, Anchor],
        connection_type: ConnectionType | None = None,
    ) -> None:
        """Register a connection between pieces."""
        base_id, target_id = piece_ids
        base_anchor, target_anchor = anchors

        # Use VanillaConnection as default if not specified
        conn_type = (
            connection_type if connection_type is not None else VanillaConnection()
        )

        connection = Connection(
            base=BoundAnchor(piece=self.pieces[base_id], anchor=base_anchor),
            target=BoundAnchor(piece=self.pieces[target_id], anchor=target_anchor),
            type=conn_type,
        )

        self.connections.append(connection)

    def piece_ref(self, items: list[Token]) -> str:
        """Transform a piece reference."""
        return str(items[0])

    def anchor_props(self, items: list[Any]) -> dict[str, Any]:
        """Transform anchor properties."""
        if not items:
            return {}
        return items[0] if items else {}

    def anchor_prop_list(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Combine multiple anchor properties."""
        result = {}
        for prop in items:
            result.update(prop)
        return result

    def anchor_prop(self, items: list[Any]) -> dict[str, Any]:
        """Transform a single anchor property."""
        key = self._unescape_string(items[0])
        value = items[1]

        # If the value is an ESCAPED_STRING token, unescape it
        if hasattr(value, "type") and value.type == "ESCAPED_STRING":
            value = self._unescape_string(value)

        return {key: value}

    def offset_value(self, items: list[Any]) -> Offset:
        """Transform an offset value."""
        offset_type = None
        value = None

        for item in items:
            if not isinstance(item, Token):
                continue

            match item.type:
                case "FROM_MIN":
                    offset_type = "FromMin"
                case "FROM_MAX":
                    offset_type = "FromMax"
                case "NUMBER":
                    value = float(item)

        if value is None:
            raise DSLValidationError("Offset value is required")

        if offset_type is None:
            raise DSLValidationError(f"Invalid offset type in items: {items}")

        return self._create_offset(offset_type, value)

    def _create_offset(self, offset_type: str, value: float) -> Offset:
        """Create an Offset instance based on type."""
        match offset_type:
            case "FromMin":
                return FromMin(value=value)
            case "FromMax":
                return FromMax(value=value)
            case _:
                raise DSLValidationError(f"Unknown offset type: {offset_type}")

    def value(self, items: list[Any]) -> Any:
        """Transform a value (string, number, or offset)."""
        item = items[0]
        if isinstance(item, Token):
            if item.type == "ESCAPED_STRING":
                return self._unescape_string(item)
            elif item.type == "NUMBER":
                return float(item)
        return item

    def _create_anchor(self, props: dict[str, Any]) -> Anchor:
        """Create an Anchor from properties."""
        contact_face = props.get("contact_face")
        edge_shared_face = props.get("edge_shared_face")
        offset = props.get("offset")

        if not contact_face:
            raise DSLValidationError("Anchor must have 'contact_face' property")
        if not edge_shared_face:
            raise DSLValidationError("Anchor must have 'edge_shared_face' property")
        if not offset:
            raise DSLValidationError("Anchor must have 'offset' property")

        if not isinstance(offset, Offset):
            raise DSLValidationError(f"Invalid offset type: {type(offset)}")

        return Anchor(
            contact_face=contact_face,
            edge_shared_face=edge_shared_face,
            offset=offset,
        )

    def _unescape_string(self, token: Token) -> str:
        """Unescape a string token."""
        # Remove quotes and handle escapes
        value = str(token)
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        # Handle common escapes
        value = value.replace('\\"', '"')
        value = value.replace("\\n", "\n")
        value = value.replace("\\t", "\t")
        value = value.replace("\\\\", "\\")
        return value

    def compact_anchor_props(self, items: list[Any]) -> Anchor:
        """Transform compact anchor properties into an Anchor object."""
        if len(items) != 3:
            raise DSLValidationError(
                f"Compact anchor must have exactly 3 components, got {len(items)}"
            )

        contact_face = self._parse_compact_face(items[0], "contact")
        edge_shared_face = self._parse_compact_face(items[1], "edge_shared")
        offset = items[2]

        if not isinstance(offset, Offset):
            raise DSLValidationError(f"Invalid offset type: {type(offset)}")

        return Anchor(
            contact_face=contact_face, edge_shared_face=edge_shared_face, offset=offset
        )

    def _parse_compact_face(self, token: Any, context: str) -> Face:
        """Parse a compact face token."""
        if not isinstance(token, Token) or token.type != "COMPACT_FACE":
            raise DSLValidationError(f"Invalid {context} face token: {token}")

        face_char = str(token)
        if face_char not in self.FACE_MAPPING:
            raise DSLValidationError(f"Invalid compact face notation: {face_char}")

        return cast(Face, self.FACE_MAPPING[face_char])

    def compact_offset(self, items: list[Any]) -> Offset:
        """Transform compact offset notation into an Offset object."""
        if len(items) != 2:
            raise DSLValidationError(
                f"Compact offset must have exactly 2 components, got {len(items)}"
            )

        offset_type_token = items[0]
        number_token = items[1]

        # Validate number token
        if not isinstance(number_token, Token) or number_token.type != "NUMBER":
            raise DSLValidationError(f"Invalid number token: {number_token}")
        if not isinstance(offset_type_token, Token):
            raise DSLValidationError(
                f"Invalid compact offset type: {offset_type_token}"
            )

        # Use match for cleaner offset type handling
        value = float(number_token)
        match offset_type_token.type:
            case "COMPACT_FROM_MIN":
                return FromMin(value=value)
            case "COMPACT_FROM_MAX":
                return FromMax(value=value)
            case _:
                raise DSLValidationError(
                    f"Unknown offset type: {offset_type_token.type}"
                )

    # ConnectionType transformers (JSON format)
    def connection_body(self, items: list[Any]) -> list[Any]:
        """Pass through connection body items."""
        return items

    def connection_type_props(self, items: list[Any]) -> ConnectionType:
        """Transform connection type properties."""
        return items[0]

    def connection_type_content(self, items: list[Any]) -> ConnectionType:
        """Transform connection type content."""
        return items[0]

    def type_vanilla(self, items: list[Any]) -> VanillaConnection:
        """Transform vanilla connection type."""
        return VanillaConnection()

    def type_dowel(self, items: list[Any]) -> DowelConnection:
        """Transform dowel connection type."""
        radius, depth = self._extract_numbers(items)
        return DowelConnection(radius=radius, depth=depth)

    def type_screw(self, items: list[Any]) -> ScrewConnection:
        """Transform screw connection type (JSON format)."""
        diameter, length = self._extract_numbers(items)
        return ScrewConnection(diameter=diameter, length=length)

    # ConnectionType transformers (Compact format)
    def compact_connection_type(self, items: list[Any]) -> ConnectionType:
        """Transform compact connection type."""
        if not items:
            return VanillaConnection()
        item = items[0]
        if isinstance(item, Token) and item.type == "COMPACT_VANILLA":
            return VanillaConnection()
        # At this point, item should be a DowelConnection or ScrewConnection
        if isinstance(item, (DowelConnection, ScrewConnection)):
            return item
        return VanillaConnection()  # fallback

    def dowel_compact(self, items: list[Any]) -> DowelConnection:
        """Transform compact dowel connection type.

        Supports both numeric format D(radius, depth) and
        preset format D(:diameterxlength).
        """
        return self._extract_connection_type(items, DowelConnection, "dowel")

    def dowel_numeric(self, items: list[Any]) -> DowelConnection:
        """Transform numeric dowel format D(radius, depth)."""
        radius, depth = self._extract_numbers(items)
        return DowelConnection(radius=radius, depth=depth)

    def dowel_preset(self, items: list[Any]) -> DowelConnection:
        """Transform preset dowel format D(:diameterxlength)."""
        diameter, length = self._extract_numbers(items)

        # Validate the preset exists
        preset = find_dowel_preset(diameter, length)
        if preset is None:
            raise DSLValidationError(
                f"Unknown dowel preset: {int(diameter)}x{int(length)}"
            )

        # Convert diameter to radius for DowelConnection
        return DowelConnection(radius=diameter / 2, depth=length)

    def screw_compact(self, items: list[Any]) -> ScrewConnection:
        """Transform compact screw connection type.

        Supports both numeric format S(diameter, length) and
        preset format S(Slim:diameter x length) or S(Coarse:diameter x length).
        """
        return self._extract_connection_type(items, ScrewConnection, "screw")

    def screw_numeric(self, items: list[Any]) -> ScrewConnection:
        """Transform numeric screw notation: S(diameter, length)."""
        diameter, length = self._extract_numbers(items)
        return ScrewConnection(diameter=diameter, length=length)

    def screw_preset(self, items: list[Any]) -> ScrewConnection:
        """Transform preset screw notation: Slim:3.3x50 or Coarse:3.8x57."""
        # Extract screw type
        screw_type: str | None = None
        for item in items:
            if self._is_token_type(item, "SCREW_TYPE"):
                screw_type = str(item)
                break

        if screw_type is None:
            raise DSLValidationError("Screw preset must specify type (Slim or Coarse)")

        diameter, length = self._extract_numbers(items)

        # Validate the preset exists
        preset = find_screw_preset(screw_type, diameter, length)
        if preset is None:
            raise DSLValidationError(
                f"Unknown {screw_type} screw preset: {diameter}x{int(length)}"
            )

        return ScrewConnection(diameter=diameter, length=length)
