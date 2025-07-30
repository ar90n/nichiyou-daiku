"""AST transformer for converting Lark parse trees to nichiyou-daiku models."""

from typing import Any, cast

from lark import Token, Transformer

from nichiyou_daiku.core.connection import Anchor, Connection
from nichiyou_daiku.core.geometry.face import Face
from nichiyou_daiku.core.geometry.offset import FromMax, FromMin, Offset
from nichiyou_daiku.core.model import Model, PiecePair
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.dsl.exceptions import DSLSemanticError, DSLValidationError


class DSLTransformer(Transformer):
    """Transform Lark parse trees into nichiyou-daiku models."""

    # Face mapping for compact notation
    FACE_MAPPING = {
        "T": "top",
        "D": "bottom",
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
        # Parse piece definition components
        piece_id = None
        piece_type = None
        props = {}
        length_value = None

        for item in items:
            if isinstance(item, Token) and item.type == "CNAME":
                piece_id = str(item)
            elif isinstance(item, Token) and item.type == "PIECE_TYPE":
                try:
                    piece_type = PieceType.of(str(item))
                except ValueError:
                    raise DSLValidationError(f"Invalid piece type: {item}")
            elif isinstance(item, dict):
                props = item
            elif isinstance(item, float) or isinstance(item, int):
                # Direct length value from compact notation
                length_value = float(item)

        if piece_type is None:
            raise DSLSemanticError("Piece type is required")

        # Extract length - either from props or direct value
        if length_value is None:
            length = props.get("length")
            if length is None:
                raise DSLValidationError("Piece must have a 'length' property")
            try:
                length_value = float(length)
            except (TypeError, ValueError):
                raise DSLValidationError(f"Invalid length value: {length}")

        # Create piece
        piece = Piece.of(piece_type, length_value, piece_id)
        if piece.id in self.pieces:
            raise DSLSemanticError(f"Duplicate piece ID: {piece_id}")

        # Store piece
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
        # Extract piece references and anchor properties
        piece_refs = []
        anchor_props_list = []
        compact_anchor_list = []

        for item in items:
            if isinstance(item, str):  # piece_ref
                piece_refs.append(item)
            elif isinstance(item, dict):  # anchor_props (JSON format)
                anchor_props_list.append(item)
            elif isinstance(item, Anchor):  # Already transformed compact anchor
                compact_anchor_list.append(item)

        if len(piece_refs) != 2:
            raise DSLSemanticError("Connection must have exactly two piece references")

        # Determine which format was used
        if anchor_props_list and not compact_anchor_list:
            # Traditional JSON format
            if len(anchor_props_list) != 2:
                raise DSLSemanticError(
                    "Connection must have exactly two anchor property sets"
                )
            lhs_anchor = self._create_anchor(anchor_props_list[0])
            rhs_anchor = self._create_anchor(anchor_props_list[1])
        elif compact_anchor_list and not anchor_props_list:
            # Compact format
            if len(compact_anchor_list) != 2:
                raise DSLSemanticError(
                    "Connection must have exactly two compact anchor definitions"
                )
            lhs_anchor = compact_anchor_list[0]
            rhs_anchor = compact_anchor_list[1]
        else:
            raise DSLSemanticError(
                "Connection must use either JSON format or compact format, not both"
            )

        # Resolve piece references
        base_id, target_id = piece_refs
        base_piece = self.pieces.get(base_id)
        target_piece = self.pieces.get(target_id)

        if base_piece is None:
            raise DSLSemanticError(f"Unknown piece reference: {base_id}")
        if target_piece is None:
            raise DSLSemanticError(f"Unknown piece reference: {target_id}")

        # Create connection
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
        # With the updated grammar, items will contain:
        # [Token(FROM_MIN/FROM_MAX, 'FromMin'/'FromMax'), Token(NUMBER, '...')]
        offset_type = None
        value = None

        for item in items:
            if hasattr(item, "type"):
                if item.type == "FROM_MIN":
                    offset_type = "FromMin"
                elif item.type == "FROM_MAX":
                    offset_type = "FromMax"
                elif item.type == "NUMBER":
                    value = float(item)

        if value is None:
            raise DSLValidationError("Offset value is required")

        if offset_type == "FromMin":
            return FromMin(value=value)
        elif offset_type == "FromMax":
            return FromMax(value=value)
        else:
            raise DSLValidationError(f"Invalid offset type in items: {items}")

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
        # items should contain: [contact_face, edge_shared_face, offset]
        if len(items) != 3:
            raise DSLValidationError(
                f"Compact anchor must have exactly 3 components, got {len(items)}"
            )

        contact_face_token = items[0]
        edge_shared_face_token = items[1]
        offset = items[2]  # Already transformed by compact_offset

        # Map compact face notation to full names
        if (
            not isinstance(contact_face_token, Token)
            or contact_face_token.type != "COMPACT_FACE"
        ):
            raise DSLValidationError(
                f"Invalid contact face token: {contact_face_token}"
            )
        if (
            not isinstance(edge_shared_face_token, Token)
            or edge_shared_face_token.type != "COMPACT_FACE"
        ):
            raise DSLValidationError(
                f"Invalid edge shared face token: {edge_shared_face_token}"
            )

        contact_face_char = str(contact_face_token)
        edge_shared_face_char = str(edge_shared_face_token)

        if contact_face_char not in self.FACE_MAPPING:
            raise DSLValidationError(
                f"Invalid compact face notation: {contact_face_char}"
            )
        if edge_shared_face_char not in self.FACE_MAPPING:
            raise DSLValidationError(
                f"Invalid compact face notation: {edge_shared_face_char}"
            )

        contact_face = cast(Face, self.FACE_MAPPING[contact_face_char])
        edge_shared_face = cast(Face, self.FACE_MAPPING[edge_shared_face_char])

        if not isinstance(offset, Offset):
            raise DSLValidationError(f"Invalid offset type: {type(offset)}")

        return Anchor(
            contact_face=contact_face, edge_shared_face=edge_shared_face, offset=offset
        )

    def compact_offset(self, items: list[Any]) -> Offset:
        """Transform compact offset notation into an Offset object."""
        # items should contain: [COMPACT_FROM_MIN/COMPACT_FROM_MAX, NUMBER]
        if len(items) != 2:
            raise DSLValidationError(
                f"Compact offset must have exactly 2 components, got {len(items)}"
            )

        offset_type_token = items[0]
        number_token = items[1]

        if not isinstance(number_token, Token) or number_token.type != "NUMBER":
            raise DSLValidationError(f"Invalid number token: {number_token}")

        value = float(number_token)

        if isinstance(offset_type_token, Token):
            if offset_type_token.type == "COMPACT_FROM_MIN":
                return FromMin(value=value)
            elif offset_type_token.type == "COMPACT_FROM_MAX":
                return FromMax(value=value)

        raise DSLValidationError(f"Invalid compact offset type: {offset_type_token}")
