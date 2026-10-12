# nichiyou-daiku LLM Prompts

Prompts for generating nichiyou-daiku furniture designs with an LLM. The prompt carries only LLM-specific guidance; the specifications live in `docs/` and are sent alongside it.

## Files

```
prompts/
├── README.md            # This file
├── system.md            # System prompt: output format, verified patterns, length rules, checklist
├── user-template.md     # Specification template to fill in
└── examples/
    ├── user-specs/      # Example specifications
    ├── nd-output/       # Expected .nd outputs (validated by the test suite)
    └── python-output/   # Expected Python output (built by the test suite)
```

## Usage

| Output | Send as the system prompt | About |
|--------|---------------------------|-------|
| `.nd` (recommended) | `prompts/system.md` + `docs/dsl-specification.md` | 7,800 tokens |
| Python | the above + `docs/api-specification.md` | 14,600 tokens |

Estimates are characters / 4. Add a file from `examples/nd-output/` when a worked example helps.

```python
from pathlib import Path

import anthropic

system = "\n\n".join(
    Path(path).read_text()
    for path in ("prompts/system.md", "docs/dsl-specification.md")
)
response = anthropic.Anthropic().messages.create(
    model="claude-sonnet-5",
    max_tokens=8192,
    system=system,
    messages=[{"role": "user", "content": Path("my-spec.md").read_text()}],
)
print(response.content[0].text)
```

## Workflow

1. Copy `user-template.md` and fill in the furniture (see `examples/user-specs/`).
2. Send it with the system prompt above.
3. Check the result:

```bash
nichiyou-daiku validate generated.nd
nichiyou-daiku report generated.nd -o report.md
```
