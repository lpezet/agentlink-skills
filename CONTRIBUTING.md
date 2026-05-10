# Contributing

## Prerequisites

- Python 3.9+
- `pip install pyyaml cryptography`
- [Claude Code](https://claude.ai/code) CLI (for Claude Code testing)
- [Hermes Agent](https://hermes-agent.nousresearch.com/) CLI (for Hermes testing)

## Repo layout

```
skills/
  <skill-name>/
    SKILL.md          ← skill definition + LLM instructions
    scripts/          ← helper scripts called from SKILL.md (optional)
      *.py
```

Each skill is self-contained in its directory. Scripts are plain Python using
only stdlib, `pyyaml`, and `cryptography` — no other dependencies.

## Anatomy of a skill

`SKILL.md` has two parts:

**Frontmatter** (YAML between `---` delimiters):

```yaml
---
name: skill-name # matches the directory name
description: |
  One-paragraph summary for discovery.
allowed-tools: Bash(python3 *), Bash(curl *)
arguments: [arg1, arg2] # positional args the skill accepts
version: 1.0.0
author: your@email.com
metadata:
  hermes:
    tags: [tag1, tag2]
    category: auth|data|util|...
---
```

**Body** — plain English instructions for the LLM. Reference scripts as
`${CLAUDE_SKILL_DIR}/scripts/<script>.py`. Always end with a Step that emits
a JSON output block (success and failure shapes both documented).

### Conventions

- Skill directory name = `name` field in frontmatter.
- Group related skills under a common prefix (e.g. `botcha-ai`, `botcha-ai-reputation`).
- Scripts output a single JSON object to stdout. Never emit partial output or progress lines.
- Always include a `"success": bool` field in every output path.
- Include a `"strategy_notes"` field on failure for debugging.
- Mark sensitive fields in docstrings (e.g. `private_key_pem`) — never log them.
- Config files live under `~/.config/<skill-prefix>/`, mode `0600`.

## Testing with Claude Code

Point Claude Code at the local repo by adding it as a marketplace source:

```bash
# In Claude Code
/plugin marketplace add file:///path/to/agentlink-skills
/plugin install <skill-name>@agentlink-skills
```

To reload after edits, reinstall the skill:

```bash
/plugin install <skill-name>@agentlink-skills
```

## Testing with Hermes Agent

Point Hermes at the local checkout instead of the GitHub remote:

```bash
hermes skills tap add /path/to/agentlink-skills
hermes skills install local/<skill-name>
/reset
```

After editing a skill, reinstall to pick up changes:

```bash
hermes skills install local/<skill-name>
/reset
```

To switch back to the published version:

```bash
hermes skills tap remove local
hermes skills tap add lpezet/agentlink-skills
hermes skills install lpezet/agentlink-skills/<skill-name>
/reset
```

## Adding a skill to the README

When a skill is ready, add an entry to the `## Skills` section in `README.md`:

```markdown
### [skill-name](skills/skill-name/SKILL.md)

**Category:** <category> | **Tags:** <tags> | **Version:** <version>

One-sentence description.

**Inputs:**

| Parameter | Required | Description |
| --------- | -------- | ----------- |
| ...       | yes/no   | ...         |

**Output:** brief description of the JSON block.
```

## Pull requests

- One skill per PR where possible.
- Verify the skill works end-to-end in at least one runtime (Claude Code or Hermes) before opening a PR.
- Keep `SKILL.md` instructions deterministic — avoid phrasing that leaves the LLM guessing.
