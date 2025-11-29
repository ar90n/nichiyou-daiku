"""Lark grammar definition for the nichiyou-daiku DSL."""

GRAMMAR = r"""
start: statement+

statement: piece_def | connection_def

piece_def: "(" CNAME? ":" PIECE_TYPE (piece_props | compact_length) ")"
PIECE_TYPE: "1x4" | "2x4"
piece_props: "{" prop_list? "}"
compact_length: "=" NUMBER
prop_list: prop ("," prop)*
prop: ESCAPED_STRING ":" value

connection_def: piece_ref "-[" connection_body "]-" piece_ref
connection_body: anchor_props anchor_props connection_type_props?
               | compact_anchor_props compact_anchor_props compact_connection_type?
piece_ref: CNAME
anchor_props: "{" anchor_prop_list? "}"
anchor_prop_list: anchor_prop ("," anchor_prop)*
anchor_prop: ESCAPED_STRING ":" (ESCAPED_STRING | offset_value)

offset_value: FROM_MIN "(" NUMBER ")" | FROM_MAX "(" NUMBER ")"

FROM_MIN: "FromMin"
FROM_MAX: "FromMax"

value: ESCAPED_STRING | NUMBER | offset_value

// Compact notation support
compact_anchor_props: COMPACT_FACE COMPACT_FACE compact_offset
compact_offset: COMPACT_FROM_MIN NUMBER | COMPACT_FROM_MAX NUMBER

COMPACT_FACE: /[TDLRFB]/
COMPACT_FROM_MIN: "<"
COMPACT_FROM_MAX: ">"

// ConnectionType (JSON)
connection_type_props: "{" connection_type_content "}"
connection_type_content: type_vanilla | type_dowel | type_screw
type_vanilla: "\"type\"" ":" "\"vanilla\""
type_dowel: "\"type\"" ":" "\"dowel\"" "," "\"radius\"" ":" NUMBER "," "\"depth\"" ":" NUMBER
type_screw: "\"type\"" ":" "\"screw\"" "," "\"diameter\"" ":" NUMBER "," "\"length\"" ":" NUMBER

// ConnectionType (Compact)
compact_connection_type: COMPACT_VANILLA | dowel_compact | screw_compact
COMPACT_VANILLA: "V"
dowel_compact: DOWEL_START (dowel_preset | dowel_numeric) ")"
DOWEL_START: "D("
dowel_numeric: NUMBER "," NUMBER
dowel_preset: ":" NUMBER "x" NUMBER
screw_compact: SCREW_START (screw_preset | screw_numeric) ")"
SCREW_START: "S("
screw_numeric: NUMBER "," NUMBER
screw_preset: SCREW_TYPE ":" NUMBER "x" NUMBER
SCREW_TYPE: "Slim" | "Coarse"

// Comment support
COMMENT: "//" /[^\n]*/

%import common.CNAME
%import common.NUMBER
%import common.ESCAPED_STRING
%import common.WS
%ignore WS
%ignore COMMENT
"""
