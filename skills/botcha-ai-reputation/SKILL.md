---
name: botcha-ai-reputation
description: |
  Read a Botcha.ai agent's reputation score and event history. Supports two operations:
    get  — fetch current score (0-1000) and trust tier
    list — retrieve the agent's event history, optionally filtered by category

  Prerequisite: the agent must already be registered via /botcha-ai-agent
  (identity in ~/.config/botcha-ai/agent.yml and config.yml).

  Call with:
    app_id:    <Botcha.ai app ID>           [required]
    operation: get | list                   [required]
    category:  verification | attestation | delegation |
               session | violation | endorsement       [optional filter for list]
    limit:     <integer>                   [optional for list]

  Returns a JSON block with operation-specific fields — see Step 4.
context: fork
allowed-tools: Bash(python3 *)
arguments:
  - app_id
  - operation
  - category
  - limit
argument-hint: <app_id> <get|list> [<category>] [<limit>]
version: 1.0.0
author: lpezet@gmail.com
metadata:
  hermes:
    tags: [auth, botcha.ai, reputation, trust]
    category: auth
---

Your sole job: execute the requested reputation operation and return the result as a JSON block.

Parameters: `$app_id` (required), `$operation` = `get|list` (required), `$category` (optional), `$limit` (optional).

Config dir: `~/.config/botcha-ai/`  
Scripts: `${CLAUDE_SKILL_DIR}/scripts/`

## CRITICAL RULES

1. **NEVER use curl** — use the pre-built scripts for all API calls.
2. **Every** API call in the scripts already includes `?app_id=<app_id>` — do not add it manually.
3. The `private_key_pem` in `agent.yml` is sensitive. Never log or emit it.
4. If config files are missing, tell the user to run **/botcha-ai-agent $app_id** first.
5. **Do not obtain or pass tokens yourself.** Auth is fully self-managed: the scripts try TAP
   challenge-response first, fall back to puzzle-solving, and cache the resulting token (with
   its expiry and type — `tap` or `challenge`) in `~/.config/botcha-ai/config.yml`. The cached
   token is reused automatically on subsequent calls until near expiry.

---

## Background

Reputation scores reflect verified behavior — they cannot be self-reported. Events are
recorded internally by Botcha.ai (e.g. when a challenge is solved via `botcha-ai-challenge`
or a TAP auth succeeds via `botcha-ai-token`) or by other agents reporting on interactions
(endorsements, delegations).

The primary way an agent builds reputation today is through `botcha-ai-challenge` and
`botcha-ai-token`: each successful challenge-response or TAP auth contributes `verification`
events that raise the score. The Botcha.ai whitepaper describes a planned **reputation marketplace** where agents
will earn reputation across partner networks — today's score is the foundation for that.

When reporting results to the user, briefly explain what the score means in this context.

---

## Operation: get

Fetch the agent's current reputation score and tier.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_reputation_get.py $app_id
```

**If `"success": true`** → go to Step 4.  
**If `"success": false`** with `config_load_failed` → tell the user to run **/botcha-ai-agent $app_id** first. Stop.  
**If `"success": false`** with any other error → go to Step 4 (failure output).

---

## Operation: list

List the agent's reputation event history.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_reputation_events.py $app_id
```

With optional category filter:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_reputation_events.py $app_id $category
```

With category and limit:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_reputation_events.py $app_id $category $limit
```

Omit category but include limit by passing an empty string: `"" $limit`.

**If `"success": true`** → go to Step 4.  
**If `"success": false`** → go to Step 4 (failure output).

---

## Step 4: Emit output

**Always emit this JSON block, even on failure.**

### get (success)

```json
{
  "success": true,
  "operation": "get",
  "agent_id": "agent_...",
  "score": 350,
  "tier": "verified",
  "events": 12
}
```

### list (success)

```json
{
  "success": true,
  "operation": "list",
  "agent_id": "agent_...",
  "events": [
    {"id": "evt_...", "category": "verification", "action": "auth_success", "ts": "..."},
    ...
  ]
}
```

### failure (any operation)

```json
{
  "success": false,
  "operation": "get|list",
  "error": "...",
  "raw_response": "...",
  "strategy_notes": "be specific: what failed and what you tried"
}
```
