---
name: botcha-ai-reputation
description: |
  Manage a Botcha.ai agent's reputation score. Supports three operations:
    get    — fetch current score (0-1000) and trust tier
    record — post a reputation event (positive or negative) to grow or signal trust
    list   — retrieve the agent's event history, optionally filtered by category

  Prerequisite: the agent must already be registered via the botcha-ai skill
  (identity in ~/.config/botcha-ai/agent.yml and config.yml).

  Call with:
    app_id:    <Botcha.ai app ID>           [required]
    operation: get | record | list          [required]
    category:  verification | attestation | delegation |
               session | violation | endorsement       [required for record; optional filter for list]
    action:    <action type>                [required for record — see table below]
    metadata:  <JSON string>               [optional for record]
    limit:     <integer>                   [optional for list]

  Returns a JSON block with operation-specific fields — see Step 4.
allowed-tools: Bash(python3 *)
arguments: [app_id, operation, category, action, metadata, limit]
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

## Action reference

| Category       | Actions                                                              |
|----------------|----------------------------------------------------------------------|
| verification   | challenge_solved, challenge_failed, auth_success, auth_failure       |
| attestation    | attestation_issued, attestation_verified, attestation_revoked        |
| delegation     | delegation_granted, delegation_received, delegation_revoked          |
| session        | session_created, session_expired, session_terminated                 |
| violation      | rate_limit_exceeded, invalid_token, abuse_detected                   |
| endorsement    | endorsement_received, endorsement_given                              |

Positive events (raise score): challenge_solved, auth_success, attestation_verified,
attestation_issued, delegation_granted, delegation_received, session_created,
endorsement_received, endorsement_given.

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

## Operation: record

Record a reputation event for the agent. Requires `category` and `action` (see table above).
Optionally accepts a `metadata` JSON string (e.g. `'{"transaction_amount": 42.50}'`).

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_reputation_event.py $1 CATEGORY ACTION
```

With metadata:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_reputation_event.py $1 CATEGORY ACTION 'METADATA_JSON'
```

The script handles authentication internally (TAP first, speed-challenge fallback).

**If `"success": true`** → go to Step 4.  
**If `"success": false`** with `auth_failed` → report auth failure and stop. Do not retry.  
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

### record (success)

```json
{
  "success": true,
  "operation": "record",
  "event_id": "evt_...",
  "score": 375
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
  "operation": "get|record|list",
  "error": "...",
  "raw_response": "...",
  "strategy_notes": "be specific: what failed and what you tried"
}
```
