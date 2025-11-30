# nichiyou-daiku LLM Prompts

This directory contains prompts for generating nichiyou-daiku design code using LLMs.

## Files

```
prompts/
├── README.md           # This file
├── system.md           # System prompt (provide to LLM first)
├── user-template.md    # User input template
└── examples/           # Filled-in examples
    ├── side-table.md
    └── two-tier-shelf.md
```

## Usage

### 1. Set System Prompt

Provide the contents of `system.md` as the LLM's system prompt (or context).

### 2. Fill in Specification

Copy `user-template.md` and fill in your furniture specifications.

### 3. Send to LLM

Send the filled specification to the LLM. It will generate ND script or Python code.

## Example

### Using ChatGPT / Claude

1. Start a new conversation
2. Send `system.md` content first (or prefix with "This is the system prompt:")
3. Send your filled specification
4. Receive generated code

### Using API

```python
import anthropic  # or openai

system_prompt = open("prompts/system.md").read()
user_message = open("your-spec.md").read()

# Claude API example
client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    system=system_prompt,
    messages=[{"role": "user", "content": user_message}]
)
print(response.content[0].text)
```

## Tips

- **Output format**: Use `nd` for simple structures, `python` for complex calculations
- **Dimensions**: Specify in mm (approximations OK, LLM will calculate accounting for lumber sizes)
- **Notes**: Include any special requirements or preferences
