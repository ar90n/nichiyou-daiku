# nichiyou-daiku LLM Prompts

Prompts for generating nichiyou-daiku furniture design code using LLMs (Claude Sonnet 4.5, GPT-4.5, Gemini 3.0, etc.).

## Directory Structure

```
prompts/
├── README.md                    # This file
├── system.md                    # Core system prompt (~390 lines)
├── user-template.md             # User input template
│
├── reference/                   # Optional reference documents
│   ├── presets.md               # All fastener presets
│   ├── dsl-complete.md          # Grammar, JSON notation, errors, CLI (supplements system.md)
│   └── python-api.md            # Complete Python API (needed for Python output)
│
└── examples/
    ├── user-specs/              # User input examples
    │   ├── side-table.md
    │   └── two-tier-shelf.md
    ├── nd-output/               # Expected ND script outputs
    │   ├── side-table.nd
    │   ├── two-tier-shelf.nd
    │   └── corner-joint.nd
    └── python-output/           # Expected Python outputs
        └── simple-table.py
```

## Usage Patterns

### Pattern A: Minimal (~4,200 tokens)

For simple furniture. Uses only the core system prompt.

```python
import anthropic

system_prompt = open("prompts/system.md").read()
user_spec = open("your-spec.md").read()

client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    system=system_prompt,
    messages=[{"role": "user", "content": user_spec}]
)
print(response.content[0].text)
```

### Pattern B: Standard (~5,500 tokens) - Recommended

Includes fastener preset reference for better accuracy.

```python
system_prompt = open("prompts/system.md").read()
presets = open("prompts/reference/presets.md").read()

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    system=system_prompt + "\n\n" + presets,
    messages=[{"role": "user", "content": user_spec}]
)
```

### Pattern C: Full (~7,500 tokens)

For complex designs requiring complete reference.

```python
system_prompt = open("prompts/system.md").read()
presets = open("prompts/reference/presets.md").read()
dsl_spec = open("prompts/reference/dsl-complete.md").read()
example = open("prompts/examples/nd-output/side-table.nd").read()

full_context = f"{system_prompt}\n\n{presets}\n\n{dsl_spec}\n\n## Example Output\n```nd\n{example}\n```"

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    system=full_context,
    messages=[{"role": "user", "content": user_spec}]
)
```

## Quick Start

### 1. Create Your Specification

Copy `user-template.md` and fill in your furniture details:

```markdown
# Furniture Design Specification

## Basic Info
- Name: My Coffee Table
- Output format: nd

## Dimensions (mm)
- Width: 1200
- Depth: 600
- Height: 450

## Material
- Primary: 2x4

## Structure
### Legs
- Count: 4
- Position: corner inset

### Aprons
- Position: flush with top

### Top Surface
- Enabled: yes
- Material: 1x4
- Direction: width

### Shelves
- Count: 0

## Joints
- Type: dowel
- Preset: 8x30
```

### 2. Send to LLM

Using the API (see patterns above) or in a chat interface:

1. Paste `system.md` content first
2. Paste your specification
3. Receive generated ND script or Python code

### 3. Validate Output

```bash
nichiyou-daiku validate generated.nd
nichiyou-daiku report generated.nd -o report.md
```

## Token Estimates

| Pattern | Files Included | Est. Tokens |
|---------|----------------|-------------|
| Minimal | system.md | ~4,200 |
| Standard | + presets.md | ~5,500 |
| Full | + dsl-complete.md + example | ~7,500 |
| Full+ | + python-api.md | ~10,600 |

Estimates are characters / 4. The Python API lives only in `reference/python-api.md`; include it whenever you want Python output.

All patterns fit comfortably within modern LLM context windows (100K+ tokens).

## Output Formats

### ND Script (Recommended)

Simple, concise DSL. Best for most furniture.

```nd
(leg_1:2x4 =720)
(apron:2x4 =600)
leg_1 -[LB>0 DB>0 D(:8x30)]- apron
```

### Python Code

Full control for complex calculations.

```python
from nichiyou_daiku.core.piece import Piece, PieceType
piece = Piece.of(PieceType.PT_2x4, 720.0, "leg_1")
```

## Tips

1. **Be specific** about dimensions - LLM will calculate lumber lengths
2. **Choose output format** based on complexity:
   - ND for simple structures
   - Python for parametric/calculated designs
3. **Include notes** for special requirements
4. **Validate** generated code with `nichiyou-daiku validate`

## Examples

See `examples/user-specs/` for input examples and `examples/nd-output/` for expected outputs.
