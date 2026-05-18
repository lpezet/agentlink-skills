---
name: botcha-ai-token
description: |
  Obtains a Botcha.ai JWT access token for a registered TAP agent.

  Auth precedence (stops at the first success):
    1. Cached access_token — returned immediately if still valid (unless force).
    2. Refresh token — POST /v1/token/refresh (unless force).
    3. TAP challenge-response — Ed25519 nonce-sign via /v1/agents/auth.

  Requires a registered agent_id in ~/.config/botcha-ai/config.yml for the
  given app_id. Run /botcha-ai-agent first if the agent is not yet registered.
  If app_id is omitted, defaults to the first app in ~/.config/botcha-ai/config.yml.

  Returns a JSON block with access_token, refresh_token, expires_in, and
  auth_method (cached | refresh | tap).
context: fork
allowed-tools: Bash(python3 *)
arguments:
  - app_id
  - audience
  - force
argument-hint: "[<app_id>] [<audience>] [force]"
version: 1.0.0
author: lpezet@gmail.com
metadata:
  hermes:
    tags: [auth, botcha.ai, token]
    category: auth
---

Your sole job: return a valid `access_token` for `$app_id`. Stop as soon as you have one.

Parameters: `$app_id` (optional), `$audience` (optional), `$force` = `"force"` (optional).
If `$app_id` is omitted, default to the first app in `~/.config/botcha-ai/config.yml`.

Scripts: `${CLAUDE_SKILL_DIR}/scripts/` — Hermes: replace with the path to this skill's `scripts/` directory.

## CRITICAL RULE

The `private_key_pem` in `agent.yml` is sensitive. Never log or emit it.

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

## Step 1: Obtain token

Build the command from the parameters provided:

- Base call:
  ```bash
  python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_token.py $app_id
  ```
- With audience:
  ```bash
  python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_token.py $app_id --audience $audience
  ```
- With force (skips cached and refresh paths):
  ```bash
  python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_token.py $app_id --force
  ```
- With both:
  ```bash
  python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_token.py $app_id --audience $audience --force
  ```

**If `"success": true`** → emit the output block below.

**If `"error"` contains `agent_id`** → the agent is not yet registered for this app. Tell the user to run `/botcha-ai-agent $app_id` first, then retry.

**If `"success": false` with any other error** → emit the failure block.

---

## Step 2: Emit output

```json
{
  "success": true,
  "app_id": "<resolved app_id>",
  "access_token": "...",
  "refresh_token": "...",
  "expires_in": 3600,
  "auth_method": "cached | refresh | tap"
}
```

On failure:

```json
{
  "success": false,
  "error": "<error message>",
  "strategy_notes": "<what failed and at which step>"
}
```
