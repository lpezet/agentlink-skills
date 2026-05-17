---
name: botcha-ai-agent
description: |
  Registers (or retrieves) an AI agent identity with a Botcha.ai application.

  Requires an app_id (create one first with /botcha-ai-app if needed).

  If agent_id already exists in ~/.config/botcha-ai/config.yml for the given
  app_id, returns it immediately without any API calls.

  Otherwise performs the full registration flow:
    1. Creates or loads the Ed25519 keypair in ~/.config/botcha-ai/agent.yml.
    2. Solves a speed challenge to obtain a short-lived JWT.
    3. Registers the agent identity (POST /v1/agents/register) → agent_id.
    4. Registers the TAP keypair (POST /v1/agents/register/tap).
    5. Saves agent_id to ~/.config/botcha-ai/config.yml.

  Returns a JSON block with agent_id and registered (true when a new
  registration was just performed).
context: fork
allowed-tools: Bash(python3 *)
arguments:
  - app_id
argument-hint: <app_id>
version: 1.0.0
author: lpezet@gmail.com
metadata:
  hermes:
    tags: [auth, botcha.ai, registration]
    category: auth
---

Your sole job: ensure this agent has a registered identity for `$app_id` and return it.

Parameter: `$app_id` (required) — the Botcha.ai application ID (`app_...`).

Scripts: `${CLAUDE_SKILL_DIR}/scripts/` — Hermes: replace with the path to
this skill's `scripts/` directory.

## CRITICAL RULES

1. **NEVER use curl** for any `/v1/agents/` or `/v1/token/` calls. Use the script only.
2. **Every** HTTP call to `api.botcha.ai` must include `?app_id=<app_id>` in the URL.
3. The `private_key_pem` in `agent.yml` is sensitive. Never log or emit it.

---

## Step 1: Run registration script

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_register.py $app_id
```

**If the output contains `"missing": [...]`:** ask the user for each listed
value. When asking for `agent_name`, propose your own current agent name as the
default. When asking for `operator`, propose the user's name or organisation if
you know it from context. Then re-run with the supplied values:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_register.py $app_id --agent-name "NAME" --operator "ORG"
```

**If `"success": true, "registered": true`** → a new registration was performed. Record `agent_id`.

**If `"success": true, "registered": false`** → agent already registered for this app. Record `agent_id`.

**If `"success": false`** → record `error` and `raw_response` in `strategy_notes`, emit the failure block below.

---

## Step 2: Emit output

```json
{
  "success": true,
  "app_id": "<app id>",
  "agent_id": "<agent id>",
  "registered": false
}
```

Set `"registered": true` when a new registration was performed, `false` when
an existing agent_id was returned.

On failure:

```json
{
  "success": false,
  "error": "<error message>",
  "strategy_notes": "<what failed and at which step>"
}
```
