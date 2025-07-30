"""AST transformer for converting Lark parse trees to nichiyou-daiku models."""

from dataclasses import dataclass, field
from typing import Any, cast

from lark import Token, Transformer

from nichiyou_daiku.core.connection import Anchor, Connection
from nichiyou_daiku.core.geometry.face import Face
from nichiyou_daiku.core.geometry.offset import FromMax, FromMin, Offset
from nichiyou_daiku.core.model import Model, PiecePair
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.dsl.exceptions import DSLSemanticError, DSLValidationError


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
        self.connections: list[tuple[PiecePair, Connection]] = []

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
            # Early continue for unknown types
            if not isinstance(item, (Token, dict, float, int)):
                continue
                
            if isinstance(item, Token):
                match item.type:
                    case "CNAME":
                        components.piece_id = str(item)
                    case "PIECE_TYPE":
                        components.piece_type = self._parse_piece_type(item)
                    case _:
                        continue
                continue
                
            if isinstance(item, dict):
                components.props = item
                continue
                
            if isinstance(item, (float, int)):
                components.length_value = float(item)
                continue
        
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
            raise DSLValidationError(f"Invalid length value: {components.props['length']}")

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
        pieces = self._resolve_piece_references(components.piece_refs)
        
        self._register_connection(pieces, anchors)

    def _parse_connection_components(self, items: list[Any]) -> ConnectionComponents:
        """Parse items into connection components."""
        components = ConnectionComponents()
        
        for item in items:
            # Early continue pattern
            if isinstance(item, str):
                components.piece_refs.append(item)
                continue
                
            if isinstance(item, dict):
                components.anchor_props_list.append(item)
                continue
                
            if isinstance(item, Anchor):
                components.compact_anchor_list.append(item)
                continue
        
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
        # Early return for JSON format
        if components.anchor_props_list:
            return (
                self._create_anchor(components.anchor_props_list[0]),
                self._create_anchor(components.anchor_props_list[1])
            )
        
        # Compact format
        return (
            components.compact_anchor_list[0],
            components.compact_anchor_list[1]
        )

    def _resolve_piece_references(self, piece_refs: list[str]) -> tuple[Piece, Piece]:
        """Resolve piece references to actual pieces."""
        base_id, target_id = piece_refs
        
        base_piece = self.pieces.get(base_id)
        if base_piece is None:
            raise DSLSemanticError(f"Unknown piece reference: {base_id}")
        
        target_piece = self.pieces.get(target_id)
        if target_piece is None:
            raise DSLSemanticError(f"Unknown piece reference: {target_id}")
        
        return base_piece, target_piece

    def _register_connection(
        self, pieces: tuple[Piece, Piece], anchors: tuple[Anchor, Anchor]
    ) -> None:
        """Register a connection between pieces."""
        base_piece, target_piece = pieces
        lhs_anchor, rhs_anchor = anchors
        
        connection = Connection(lhs=lhs_anchor, rhs=rhs_anchor)
        piece_pair = PiecePair(base=base_piece, target=target_piece)
        
        self.connections.append((piece_pair, connection))

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
            # Early continue for non-Token items
            if not isinstance(item, Token):
                continue
                
            match item.type:
                case "FROM_MIN":
                    offset_type = "FromMin"
                case "FROM_MAX":
                    offset_type = "FromMax"
                case "NUMBER":
                    value = float(item)
        
        # Early return for validation errors
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
        # Early return for validation
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
            contact_face=contact_face,
            edge_shared_face=edge_shared_face,
            offset=offset
        )

    def _parse_compact_face(self, token: Any, context: str) -> Face:
        """Parse a compact face token."""
        # Early return for invalid token
        if not isinstance(token, Token) or token.type != "COMPACT_FACE":
            raise DSLValidationError(f"Invalid {context} face token: {token}")
        
        face_char = str(token)
        if face_char not in self.FACE_MAPPING:
            raise DSLValidationError(f"Invalid compact face notation: {face_char}")
        
        return cast(Face, self.FACE_MAPPING[face_char])

    def compact_offset(self, items: list[Any]) -> Offset:
        """Transform compact offset notation into an Offset object."""
        # Early return for validation
        if len(items) != 2:
            raise DSLValidationError(
                f"Compact offset must have exactly 2 components, got {len(items)}"
            )
        
        offset_type_token = items[0]
        number_token = items[1]
        
        # Validate number token
        if not isinstance(number_token, Token) or number_token.type != "NUMBER":
            raise DSLValidationError(f"Invalid number token: {number_token}")
        
        value = float(number_token)
        
        # Early return for invalid token type
        if not isinstance(offset_type_token, Token):
            raise DSLValidationError(f"Invalid compact offset type: {offset_type_token}")
        
        # Use match for cleaner offset type handling
        match offset_type_token.type:
            case "COMPACT_FROM_MIN":
                return FromMin(value=value)
            case "COMPACT_FROM_MAX":
                return FromMax(value=value)
            case _:
                raise DSLValidationError(f"Unknown offset type: {offset_type_token.type}")
