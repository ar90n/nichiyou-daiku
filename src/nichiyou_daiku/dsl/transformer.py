"""AST transformer for converting Lark parse trees to nichiyou-daiku models."""

from typing import Any, cast

from lark import Token, Transformer, v_args
from lark.tree import Meta

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
from nichiyou_daiku.core.model import Model, Step
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.resolve import ResolutionError, resolve_model
from nichiyou_daiku.core.screw import as_spec as as_screw_spec
from nichiyou_daiku.core.screw import find_preset as find_screw_preset
from nichiyou_daiku.core.dowel import as_spec as as_dowel_spec
from nichiyou_daiku.core.dowel import find_preset as find_dowel_preset
from nichiyou_daiku.dsl.exceptions import DSLSemanticError, DSLValidationError

# Keys accepted in JSON property objects; "note" is a free-form annotation.
PIECE_PROPERTIES = ("length", "note")
ANCHOR_PROPERTIES = ("contact_face", "edge_shared_face", "offset")


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
        self.connections: dict[tuple[str, str], Connection] = {}
        self.variables: dict[str, float] = {}
        # Where pieces and connections are written, for errors found once the
        # whole model is known
        self.positions: dict[str | tuple[str, str], tuple[int | None, int | None]] = {}
        self.steps: list[Step] | None = None
        self.steps_position: tuple[int | None, int | None] = (None, None)

    # =========================================================================
    # Entry points
    # =========================================================================

    def start(self, items: list[Any]) -> Model:
        """Transform the start rule into a Model with its unknowns resolved."""
        try:
            model = Model.of(
                pieces=list(self.pieces.values()),
                connections=self.connections.values(),
                steps=self.steps or (),
            )
        except ValueError as error:
            # Pieces and connections were checked as they were read, so what
            # is left is the steps block
            raise DSLSemanticError(str(error), *self.steps_position) from error
        try:
            return resolve_model(model)
        except ResolutionError as error:
            key = error.piece_id if error.piece_id is not None else error.connection
            line, column = (
                self.positions.get(key, (None, None)) if key else (None, None)
            )
            raise DSLValidationError(str(error), line, column) from error

    def statement(self, items: list[Any]) -> Any:
        """Pass through statement results."""
        return items[0]

    # =========================================================================
    # Variables and arithmetic
    # =========================================================================

    def var_def(self, items: list[Any]) -> None:
        """Define a variable; statements are transformed in source order."""
        name, value = str(items[0]), items[1]
        if name in self.variables:
            raise DSLSemanticError(f"Variable '{name}' is already defined")
        self.variables[name] = value

    def var(self, items: list[Token]) -> float:
        name = str(items[0])
        if name not in self.variables:
            raise DSLSemanticError(
                f"Undefined variable '{name}' (define it before it is used)"
            )
        return self.variables[name]

    def number(self, items: list[Token]) -> float:
        return float(items[0])

    def neg(self, items: list[float]) -> float:
        return -items[0]

    def add(self, items: list[float]) -> float:
        return items[0] + items[1]

    def sub(self, items: list[float]) -> float:
        return items[0] - items[1]

    def mul(self, items: list[float]) -> float:
        return items[0] * items[1]

    def div(self, items: list[float]) -> float:
        if items[1] == 0:
            raise DSLValidationError("Division by zero")
        return items[0] / items[1]

    # =========================================================================
    # Pieces and connections
    # =========================================================================

    @v_args(meta=True)
    def piece_def(self, meta: Meta, items: list[Any]) -> None:
        """Transform a piece definition."""
        *id_token, type_token, length_or_props = items
        if isinstance(length_or_props, dict):
            length = self._length_from_props(length_or_props)
        else:
            length = length_or_props
        piece_id = str(id_token[0]) if id_token else None
        piece = Piece.of(PieceType.of(str(type_token)), length, piece_id)
        self._register_piece(piece)
        self.positions[piece.id] = _position(meta)

    # =========================================================================
    # Assembly steps
    # =========================================================================

    @v_args(meta=True)
    def steps_def(self, meta: Meta, items: list[Step]) -> None:
        """Keep the steps; they are checked once every piece is known."""
        if self.steps is not None:
            raise DSLSemanticError(
                "Only one steps block is allowed; merge them into one"
            )
        self.steps = items
        self.steps_position = _position(meta)

    def step_def(self, items: list[Any]) -> Step:
        """Transform one step: its name and the pieces it adds."""
        name, *piece_ids = items
        return Step(name=self._unescape_string(name), pieces=tuple(piece_ids))

    def _length_from_props(self, props: dict[str, Any]) -> float:
        """Extract the piece length from JSON properties."""
        if "length" not in props:
            raise DSLValidationError("Piece must have a 'length' property")

        length = props["length"]
        if not isinstance(length, (int, float)):
            raise DSLValidationError(
                f"Piece property 'length' must be a number, got {length!r}"
            )
        return float(length)

    def _register_piece(self, piece: Piece) -> None:
        """Register a piece, checking for duplicates."""
        if piece.id == "steps":
            raise DSLSemanticError(
                "'steps' names the steps block and cannot name a piece; rename the piece"
            )
        if piece.id in self.pieces:
            raise DSLSemanticError(f"Duplicate piece ID: {piece.id}")
        self.pieces[piece.id] = piece

    def piece_props(self, items: list[Any]) -> dict[str, Any]:
        """Transform piece properties into a dictionary."""
        props = items[0] if items else {}
        _reject_unknown_properties(props, PIECE_PROPERTIES, "piece")
        return props

    def prop_list(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Combine properties into a single dictionary, rejecting repeated keys."""
        result: dict[str, Any] = {}
        for prop in items:
            for key, value in prop.items():
                if key in result:
                    raise DSLValidationError(f"Duplicate property '{key}'")
                result[key] = value
        return result

    anchor_prop_list = prop_list

    def prop(self, items: list[Any]) -> dict[str, Any]:
        """Transform a single property."""
        key = self._unescape_string(items[0])
        value = items[1]
        return {key: value}

    def compact_length(self, items: list[Any]) -> float | None:
        """Transform compact length notation (=expression, or =? if unknown)."""
        return None if isinstance(items[0], Token) else items[0]

    @v_args(meta=True)
    def connection_def(self, meta: Meta, items: list[Any]) -> None:
        """Transform a connection definition."""
        base_ref, body, target_ref = items
        base_anchor, target_anchor, *connection_type = body
        base_id, target_id = self._validate_piece_references([base_ref, target_ref])

        # Mirrors Model.of, but here the error can point at this statement.
        if (base_id, target_id) in self.connections or (
            target_id,
            base_id,
        ) in self.connections:
            raise DSLSemanticError(
                f"Duplicate connection between '{base_id}' and '{target_id}': "
                "only one connection per piece pair is supported"
            )

        self.positions[(base_id, target_id)] = _position(meta)
        self.connections[(base_id, target_id)] = Connection(
            base=BoundAnchor(piece=self.pieces[base_id], anchor=base_anchor),
            target=BoundAnchor(piece=self.pieces[target_id], anchor=target_anchor),
            type=connection_type[0] if connection_type else VanillaConnection(),
        )

    def _validate_piece_references(self, piece_refs: list[str]) -> tuple[str, str]:
        """Validate piece references exist and return their IDs."""
        base_id, target_id = piece_refs

        if base_id not in self.pieces:
            raise DSLSemanticError(f"Unknown piece reference: {base_id}")

        if target_id not in self.pieces:
            raise DSLSemanticError(f"Unknown piece reference: {target_id}")

        return base_id, target_id

    def piece_ref(self, items: list[Token]) -> str:
        """Transform a piece reference."""
        return str(items[0])

    def anchor_props(self, items: list[Any]) -> Anchor:
        """Transform JSON anchor properties into an Anchor."""
        return self._create_anchor(items[0] if items else {})

    def anchor_prop(self, items: list[Any]) -> dict[str, Any]:
        """Transform a single anchor property."""
        key = self._unescape_string(items[0])
        value = items[1]

        # If the value is an ESCAPED_STRING token, unescape it
        if hasattr(value, "type") and value.type == "ESCAPED_STRING":
            value = self._unescape_string(value)

        return {key: value}

    def offset_value(self, items: list[Any]) -> Offset:
        """Transform an offset value: FromMin(expression) or FromMax(expression)."""
        kind, value = items
        if kind.type == "FROM_MIN":
            return FromMin(value=value)
        return FromMax(value=value)

    def value(self, items: list[Any]) -> Any:
        """Transform a value (string, number, or offset)."""
        item = items[0]
        if isinstance(item, Token) and item.type == "ESCAPED_STRING":
            return self._unescape_string(item)
        return item

    def _create_anchor(self, props: dict[str, Any]) -> Anchor:
        """Create an Anchor from properties."""
        _reject_unknown_properties(props, ANCHOR_PROPERTIES, "anchor")
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
        contact_face, edge_shared_face, offset = items
        return Anchor(
            contact_face=self._parse_compact_face(contact_face),
            edge_shared_face=self._parse_compact_face(edge_shared_face),
            offset=offset,
        )

    def _parse_compact_face(self, token: Token) -> Face:
        """Parse a compact face token (one of T, D, L, R, F, B)."""
        return cast(Face, self.FACE_MAPPING[str(token)])

    def compact_offset(self, items: list[Any]) -> Offset | None:
        """Transform compact offset notation (<value, >value, or ? if unknown)."""
        if len(items) == 1:
            return None
        kind, value = items
        if kind.type == "COMPACT_FROM_MIN":
            return FromMin(value=value)
        return FromMax(value=value)

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

    def type_dowel(self, items: list[float]) -> DowelConnection:
        """Transform a dowel connection type: JSON or compact D(radius, depth)."""
        radius, depth = items
        return DowelConnection(radius=radius, depth=depth)

    dowel_numeric = type_dowel

    def type_screw(self, items: list[float]) -> ScrewConnection:
        """Transform a screw connection type: JSON or compact S(diameter, length)."""
        diameter, length = items
        return ScrewConnection(diameter=diameter, length=length)

    screw_numeric = type_screw

    # ConnectionType transformers (Compact format)
    def compact_connection_type(self, items: list[Any]) -> ConnectionType:
        """Transform compact connection type: V, D(...) or S(...)."""
        item = items[0]
        return VanillaConnection() if isinstance(item, Token) else item

    def dowel_compact(self, items: list[Any]) -> DowelConnection:
        """Transform compact dowel connection type.

        Supports both numeric format D(radius, depth) and
        preset format D(:diameterxlength).
        """
        # items[0] is the DOWEL_START token.
        return items[-1]

    def dowel_preset(self, items: list[Any]) -> DowelConnection:
        """Transform preset dowel format D(:diameterxlength)."""
        diameter, length = _numbers(items)

        preset = find_dowel_preset(diameter, length)
        if preset is None:
            raise DSLValidationError(f"Unknown dowel preset: {_size_text(items)}")

        spec = as_dowel_spec(preset)
        return DowelConnection(radius=spec.diameter / 2, depth=spec.length)

    def screw_compact(self, items: list[Any]) -> ScrewConnection:
        """Transform compact screw connection type.

        Supports both numeric format S(diameter, length) and
        preset format S(Slim:diameter x length) or S(Coarse:diameter x length).
        """
        # items[0] is the SCREW_START token.
        return items[-1]

    def screw_preset(self, items: list[Any]) -> ScrewConnection:
        """Transform preset screw notation: Slim:3.3x50 or Coarse:3.8x57."""
        screw_type = str(items[0])
        diameter, length = _numbers(items)

        preset = find_screw_preset(screw_type, diameter, length)
        if preset is None:
            raise DSLValidationError(
                f"Unknown {screw_type} screw preset: {_size_text(items)}"
            )

        spec = as_screw_spec(preset)
        return ScrewConnection(
            diameter=spec.diameter, length=spec.length, screw_type=spec.screw_type
        )


def _number_tokens(items: list[Any]) -> list[Token]:
    return [item for item in items if isinstance(item, Token) and item.type == "NUMBER"]


def _numbers(items: list[Any]) -> list[float]:
    """Extract the NUMBER tokens of a rule as floats."""
    return [float(token) for token in _number_tokens(items)]


def _size_text(items: list[Any]) -> str:
    """Render a preset size exactly as written, e.g. ``8.9x30.7``."""
    return "x".join(_number_tokens(items))


def _reject_unknown_properties(
    props: dict[str, Any], allowed: tuple[str, ...], kind: str
) -> None:
    for key in props:
        if key not in allowed:
            raise DSLValidationError(
                f"Unknown {kind} property '{key}' (allowed: {', '.join(allowed)})"
            )


def _position(meta: Meta) -> tuple[int | None, int | None]:
    # An empty meta (no source position) has no line or column attributes
    return getattr(meta, "line", None), getattr(meta, "column", None)
