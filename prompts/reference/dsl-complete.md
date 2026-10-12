# Complete DSL Specification

Supplement to `system.md`, which already covers the face model, offsets, placement rules, face letters, connection types, dowel/screw rules, presets and verified patterns. This file adds only the grammar, JSON notation, comments, error messages and CLI.

## File Structure

An `.nd` file contains comments, piece definitions and connection definitions (pieces must be defined before they are referenced).

```nd
// Single-line comment
// Project: Dining Table
(leg:2x4 =720)  // End-of-line comment
(shelf:1x4 =600)
(top_board:2x4 =1200.5)  // integer or decimal length
(:1x4 =800)  // ID omitted: a UUID is generated and the piece cannot be referenced
```

## JSON Notation

Pieces and anchors can be written with full property names instead of the compact form.

```text
(piece_id:PIECE_TYPE {"length": value})
base -[{"contact_face": FACE, "edge_shared_face": FACE, "offset": FromMin(v) | FromMax(v)}
       {"contact_face": FACE, "edge_shared_face": FACE, "offset": ...} JSON_TYPE?]- target
```

`FACE` is a full face name: `"top"`, `"down"`, `"left"`, `"right"`, `"front"`, `"back"`. JSON anchors take a JSON connection type (compact anchors take `V`, `D(...)`, `S(...)`): `{"type": "vanilla"}`, `{"type": "dowel", "radius": r, "depth": total_length}`, `{"type": "screw", "diameter": d, "length": l}`. In the JSON dowel type, `depth` is the total dowel length (same meaning as the second number of `D(radius, length)`).

`leg -[FL<100 DF<0 D(:8x30)]- apron` written in JSON:

```nd
(leg:2x4 {"length": 700})
(apron:2x4 {"length": 500})
leg -[{"contact_face": "front", "edge_shared_face": "left", "offset": FromMin(100)}
      {"contact_face": "down", "edge_shared_face": "front", "offset": FromMin(0)}
      {"type": "dowel", "radius": 4, "depth": 30}]- apron
```

## More Screw Examples

```nd
(post:2x4 =600)
(rail:2x4 =400)
(cleat:2x4 =400)
// Numeric S(diameter, length): rail screwed across the post's front face
post -[FL<300 BT<0 S(3.5, 50)]- rail
// Coarse preset: cleat screwed face to face behind the post, tops flush
post -[BT<0 FT<0 S(Coarse:3.8x57)]- cleat
```

## EBNF Grammar

```ebnf
start           = statement+
statement       = piece_def | connection_def

piece_def       = "(" CNAME? ":" PIECE_TYPE (piece_props | compact_length) ")"
PIECE_TYPE      = "1x4" | "1x6" | "1x8" | "2x2" | "2x4" | "2x6"
piece_props     = "{" prop_list? "}"
compact_length  = "=" NUMBER
prop_list       = prop ("," prop)*
prop            = ESCAPED_STRING ":" value

connection_def  = piece_ref "-[" connection_body "]-" piece_ref
connection_body = anchor_props anchor_props connection_type_props?
                | compact_anchor compact_anchor compact_connection_type?
piece_ref       = CNAME

anchor_props    = "{" anchor_prop_list? "}"
anchor_prop_list= anchor_prop ("," anchor_prop)*
anchor_prop     = ESCAPED_STRING ":" (ESCAPED_STRING | offset_value)
offset_value    = "FromMin" "(" NUMBER ")" | "FromMax" "(" NUMBER ")"

connection_type_props = "{" ( '"type": "vanilla"'
                            | '"type": "dowel", "radius": ' NUMBER ', "depth": ' NUMBER
                            | '"type": "screw", "diameter": ' NUMBER ', "length": ' NUMBER ) "}"

compact_anchor  = COMPACT_FACE COMPACT_FACE compact_offset
compact_offset  = "<" NUMBER | ">" NUMBER
COMPACT_FACE    = "T" | "D" | "L" | "R" | "F" | "B"

compact_connection_type = "V" | dowel_compact | screw_compact
dowel_compact   = "D(" (dowel_preset | dowel_numeric) ")"
dowel_preset    = ":" NUMBER "x" NUMBER
dowel_numeric   = NUMBER "," NUMBER
screw_compact   = "S(" (screw_preset | screw_numeric) ")"
screw_preset    = SCREW_TYPE ":" NUMBER "x" NUMBER
screw_numeric   = NUMBER "," NUMBER
SCREW_TYPE      = "Slim" | "Coarse"

COMMENT         = "//" [^\n]*     (ignored, like whitespace)
CNAME           = /[a-zA-Z_][a-zA-Z0-9_]*/
NUMBER          = /[0-9]+(\.[0-9]+)?/
```

## Error Messages

| Error Type | Example | Cause |
|------------|---------|-------|
| DSLSyntaxError | "Syntax error at line 1, column 4: Unexpected token '3'. Expected: piece type (1x4, 1x6, 1x8, 2x2, 2x4, 2x6)" | Invalid syntax, e.g. unknown lumber type `3x4` |
| DSLSemanticError | "Unknown piece reference: foo" | Reference to an undefined piece |
| DSLSemanticError | "Duplicate piece ID: leg_1" | Same ID used twice |
| DSLSemanticError | "Duplicate connection between 'a' and 'b' ..." | Second connection for the same base/target pair |
| DSLValidationError | "contact_face 'front' and edge_shared_face 'back' must be adjacent faces" | Same or opposite faces in an anchor |
| DSLValidationError | "Offset 50.0mm exceeds piece dimension 38.0mm ..." | Offset longer than the anchor's edge |
| DSLValidationError | "Unknown dowel preset: 9x99" | Non-existent preset |
| DSLValidationError | "ScrewConnection target contact_face must be 'front' or 'back' ..." | Screw target contacts with another face |
| DSLValidationError | "Screw length 35.0mm does not reach base piece ..." | Screw not longer than the target thickness |
| DSLValidationError | "Dowel depth 20.0mm (half of 40.0mm) would go through ..." | Dowel half-length is not shorter than a piece's depth |

Error messages include the line and column of the offending statement.

## CLI Commands

```bash
# Validate the model
nichiyou-daiku validate furniture.nd

# Generate report
nichiyou-daiku report furniture.nd -o report.md

# 3D view (requires build123d)
nichiyou-daiku view furniture.nd

# Export to STL/STEP (requires build123d)
nichiyou-daiku export furniture.nd -f stl
nichiyou-daiku export furniture.nd -f step -o model.step

# Technical drawing PDF (requires build123d)
nichiyou-daiku drawing furniture.nd -o furniture.pdf
```
