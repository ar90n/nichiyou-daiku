"""Lark grammar definition for the nichiyou-daiku DSL."""

from nichiyou_daiku.core.piece import PieceType

PIECE_TYPE_NAMES = sorted(piece_type.value for piece_type in PieceType)

GRAMMAR = r"""
start: statement+

statement: piece_def | connection_def | var_def | steps_def

// Assembly steps: each names the pieces it adds, in the order they are built
steps_def: "steps" "{" step_def+ "}"
step_def: ESCAPED_STRING ":" piece_ref ("," piece_ref)*

// Variables and arithmetic: a variable must be defined before it is used
var_def: CNAME "=" sum
?sum: product | sum "+" product -> add | sum "-" product -> sub
?product: atom | product "*" atom -> mul | product "/" atom -> div
?atom: NUMBER -> number | CNAME -> var | "-" atom -> neg | "(" sum ")"

piece_def: "(" CNAME? ":" PIECE_TYPE (piece_props | compact_length) ")"
PIECE_TYPE: __PIECE_TYPES__
piece_props: "{" prop_list? "}"
// "?" leaves a length or offset for the connections to fix
compact_length: "=" (sum | UNKNOWN)
UNKNOWN: "?"
prop_list: prop ("," prop)*
prop: ESCAPED_STRING ":" value

connection_def: piece_ref "-[" connection_body "]-" piece_ref
connection_body: anchor_props anchor_props connection_type_props?
               | compact_anchor_props compact_anchor_props compact_connection_type?
piece_ref: CNAME
anchor_props: "{" anchor_prop_list? "}"
anchor_prop_list: anchor_prop ("," anchor_prop)*
anchor_prop: ESCAPED_STRING ":" (ESCAPED_STRING | offset_value)

offset_value: FROM_MIN "(" sum ")" | FROM_MAX "(" sum ")"

FROM_MIN: "FromMin"
FROM_MAX: "FromMax"

value: ESCAPED_STRING | sum | offset_value

// Compact notation support
compact_anchor_props: COMPACT_FACE COMPACT_FACE compact_offset
// A compact offset is a number, a variable or a bracketed expression. Its own
// rule keeps the next face letter (TF<0 BD<0) from being read as a name.
compact_offset: COMPACT_FROM_MIN offset_atom | COMPACT_FROM_MAX offset_atom | UNKNOWN
?offset_atom: NUMBER -> number | CNAME -> var | "(" sum ")"

COMPACT_FACE: /[TDLRFB]/
COMPACT_FROM_MIN: "<"
COMPACT_FROM_MAX: ">"

// ConnectionType (JSON)
connection_type_props: "{" connection_type_content "}"
connection_type_content: type_vanilla | type_dowel | type_screw
type_vanilla: "\"type\"" ":" "\"vanilla\""
type_dowel: "\"type\"" ":" "\"dowel\"" "," "\"radius\"" ":" sum "," "\"depth\"" ":" sum
type_screw: "\"type\"" ":" "\"screw\"" "," "\"diameter\"" ":" sum "," "\"length\"" ":" sum

// ConnectionType (Compact)
compact_connection_type: COMPACT_VANILLA | dowel_compact | screw_compact
COMPACT_VANILLA: "V"
dowel_compact: DOWEL_START (dowel_preset | dowel_numeric) ")"
DOWEL_START: "D("
dowel_numeric: sum "," sum
dowel_preset: ":" NUMBER "x" NUMBER
screw_compact: SCREW_START (screw_preset | screw_numeric) ")"
SCREW_START: "S("
screw_numeric: sum "," sum
screw_preset: SCREW_TYPE ":" NUMBER "x" NUMBER
// A screw type only when no name character follows, so SlimD is a variable
SCREW_TYPE.2: /(Slim|Coarse)(?![A-Za-z0-9_])/

// Comment support
COMMENT: "//" /[^\n]*/

%import common.CNAME
%import common.NUMBER
%import common.ESCAPED_STRING
%import common.WS
%ignore WS
%ignore COMMENT
""".replace("__PIECE_TYPES__", " | ".join(f'"{name}"' for name in PIECE_TYPE_NAMES))
