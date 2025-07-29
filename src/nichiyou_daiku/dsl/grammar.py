"""Lark grammar definition for the nichiyou-daiku DSL."""

GRAMMAR = r"""
start: statement+

statement: piece_def | connection_def

piece_def: "(" CNAME? ":" PIECE_TYPE piece_props ")"
PIECE_TYPE: "PT_1x4" | "PT_2x4"
piece_props: "{" prop_list? "}"
prop_list: prop ("," prop)*
prop: ESCAPED_STRING ":" value

connection_def: piece_ref "-[" anchor_props anchor_props "]-" piece_ref
piece_ref: CNAME
anchor_props: "{" anchor_prop_list? "}"
anchor_prop_list: anchor_prop ("," anchor_prop)*
anchor_prop: ESCAPED_STRING ":" (ESCAPED_STRING | offset_value)

offset_value: FROM_MIN "(" NUMBER ")" | FROM_MAX "(" NUMBER ")"

FROM_MIN: "FromMin"
FROM_MAX: "FromMax"

value: ESCAPED_STRING | NUMBER | offset_value

%import common.CNAME
%import common.NUMBER
%import common.ESCAPED_STRING
%import common.WS
%ignore WS
"""