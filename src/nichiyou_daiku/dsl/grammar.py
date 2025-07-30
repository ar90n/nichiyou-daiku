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

connection_def: piece_ref "-[" (anchor_props anchor_props | compact_anchor_props compact_anchor_props) "]-" piece_ref
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

// Comment support
COMMENT: "//" /[^\n]*/

%import common.CNAME
%import common.NUMBER
%import common.ESCAPED_STRING
%import common.WS
%ignore WS
%ignore COMMENT
"""
