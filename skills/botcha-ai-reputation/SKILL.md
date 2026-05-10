---
name: botcha-ai-reputation
description: |
  Read a Botcha.ai agent's reputation score and event history. Supports two operations:
    get  — fetch current score (0-1000) and trust tier
    list — retrieve the agent's event history, optionally filtered by category

  Prerequisite: the agent must already be registered via the botcha-ai skill
  (identity in ~/.config/botcha-ai/agent.yml and config.yml).

  Call with:
    app_id:    <Botcha.ai app ID>           [required]
    operation: get | list                   [required]
    category:  verification | attestation | delegation |
               session | violation | endorsement       [optional filter for list]
    limit:     <integer>                   [optional for list]

  Returns a JSON block with operation-specific fields — see Step 4.
allowed-tools: Bash(python3 *)
arguments: [app_id, operation, category, limit]
version: 1.0.0
author: lpezet@gmail.com
metadata:
  hermes:
    tags: [auth, botcha.ai, reputation, trust]
    category: auth
---

Your sole job: execute the requested reputation operation and return the result as a JSON block.

Parameters: `$1` = app_id (required), `$2` = operation (required), remaining args depend on operation.

Config dir: `~/.config/botcha-ai/`  
Scripts: `${CLAUDE_SKILL_DIR}/scripts/`

## CRITICAL RULES

1. **NEVER use curl** — use the pre-built scripts for all API calls.
2. **Every** API call in the scripts already includes `?app_id=<app_id>` — do not add it manually.
3. The `private_key_pem` in `agent.yml` is sensitive. Never log or emit it.
4. If config files are missing, tell the user to run the **botcha-ai skill** first.

---

## Background

Reputation scores reflect verified behavior — they cannot be self-reported. Events are
recorded internally by Botcha.ai (e.g. when a challenge is solved or auth succeeds via the
botcha-ai skill) or by other agents reporting on interactions (endorsements, delegations).

The primary way an agent builds reputation today is through the botcha-ai skill: each
successful challenge-response or TAP auth contributes `verification` events that raise the
score. The Botcha.ai whitepaper describes a planned **reputation marketplace** where agents
will earn reputation across partner networks — today's score is the foundation for that.

When reporting results to the user, briefly explain what the score means in this context.

---

## Operation: get

Fetch the agent's current reputation score and tier.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_reputation_get.py $1
```

**If `"success": true`** → go to Step 4.  
**If `"success": false`** with `config_load_failed` → tell the user to run the botcha-ai skill first. Stop.  
**If `"success": false`** with any other error → go to Step 4 (failure output).

---

## Operation: list

List the agent's reputation event history.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_reputation_events.py $1
```

With optional category filter:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_reputation_events.py $1 CATEGORY
```

With category and limit:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_reputation_events.py $1 CATEGORY LIMIT
```

Omit CATEGORY but include LIMIT by passing an empty string: `"" LIMIT`.

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
