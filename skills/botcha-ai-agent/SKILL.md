---
name: botcha-ai-agent
description: |
  Registers (or retrieves) an AI agent identity with a Botcha.ai application.

  Requires an app_id (create one first with /botcha-ai-app if needed).
  If app_id is omitted, defaults to the first app in ~/.config/botcha-ai/config.yml.

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
argument-hint: "[<app_id>]"
version: 1.0.0
author: lpezet@gmail.com
metadata:
  hermes:
    tags: [auth, botcha.ai, registration]
    category: auth
---

Your sole job: ensure this agent has a registered identity for `$app_id` and return it.

Parameters: `$app_id` (optional) — the Botcha.ai application ID (`app_...`).
If omitted, default to the first app in `~/.config/botcha-ai/config.yml`.

Scripts: `${CLAUDE_SKILL_DIR}/scripts/` — Hermes: replace with the path to
this skill's `scripts/` directory.

## CRITICAL RULES

1. **NEVER use curl** for any `/v1/agents/` or `/v1/token/` calls. Use the script only.
2. **Every** HTTP call to `api.botcha.ai` must include `?app_id=<app_id>` in the URL.
3. The `private_key_pem` in `agent.yml` is sensitive. Never log or emit it.

---

## Step 0: Resolve app_id

If `$app_id` was not provided, resolve it from config:

```bash
python3 -c "
import sys, json
try:
    import yaml, pathlib
    cfg = yaml.safe_load(pathlib.Path('~/.config/botcha-ai/config.yml').expanduser().read_text())
    apps = list((cfg or {}).get('apps', {}).keys())
    if not apps:
        print(json.dumps({'success': False, 'error': 'No apps in ~/.config/botcha-ai/config.yml — run /botcha-ai-app first.'}))
    else:
        print(apps[0])
except FileNotFoundError:
    print(json.dumps({'success': False, 'error': 'Config not found at ~/.config/botcha-ai/config.yml — run /botcha-ai-app first.'}))
"
```

- If the output is a JSON object with `"success": false` → emit it as the failure block and stop.
- Otherwise the output is the resolved `app_id`. Use it for all subsequent steps.

Always include the resolved `app_id` in the output block, regardless of whether it was passed explicitly or defaulted.

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
  "app_id": "<resolved app_id>",
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
