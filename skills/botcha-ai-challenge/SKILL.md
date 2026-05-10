---
name: botcha-ai-challenge
description: |
  Intentionally solve a Botcha.ai challenge to earn reputation through verified
  challenge-solving. Unlike the botcha-ai skill (which solves challenges only as a
  fallback when TAP auth fails), this skill explicitly requests and solves a fresh
  challenge — clearing any cached token first — so the verified event is always
  credited to the registered agent's reputation score.

  Only speed and compute challenges are handled automatically. If a reasoning or
  hybrid challenge is returned, the skill will tell you to use the botcha-ai skill
  instead (those require interactive input).

  Prerequisite: the agent must already be registered via the botcha-ai skill
  (identity in ~/.config/botcha-ai/agent.yml and config.yml).

  Call with:
    app_id:   <Botcha.ai app ID>    [required]
    audience: <resource server URL> [optional]

  Returns a JSON block — see Step 2.
allowed-tools: Bash(python3 *)
arguments: [app_id, audience]
version: 1.0.0
author: lpezet@gmail.com
metadata:
  hermes:
    tags: [auth, botcha.ai, reputation, challenge]
    category: auth
---

Your sole job: solve a fresh Botcha.ai challenge to earn a reputation event and return
the result as a JSON block.

Parameters: `$1` = app_id (required), `$2` = audience (optional).

Config dir: `~/.config/botcha-ai/`  
Scripts: `${CLAUDE_SKILL_DIR}/scripts/`

## CRITICAL RULES

1. **NEVER use curl** — use the pre-built script for all API calls.
2. The `private_key_pem` in `agent.yml` is sensitive. Never log or emit it.
3. If config files are missing or `agent_not_registered` is returned, tell the user
   to run the **botcha-ai skill** first. Stop.
4. This skill always clears the cached token to guarantee a fresh challenge is solved.
   Do not attempt to reuse an existing token.
5. **Rate limit: 100 challenges per hour per IP.** Never call this skill in a loop or
   in rapid succession. One call per deliberate reputation-building action. If the script
   returns `rate_limit_exceeded`, stop immediately and inform the user — do not retry.

## Background

Solving a challenge with your registered `agent_id` in the verify payload tells
Botcha.ai to credit the verification event to your reputation. This is the primary
automated way to grow reputation score — each successful solve contributes a
`verification / challenge_solved` event.

TAP challenge-response (via the botcha-ai skill) is a stronger trust signal, but
this skill is useful for proactively accumulating verification events between TAP auths.

---

## Step 1: Solve the challenge

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_challenge.py $1
```

Include `$2` if an audience was provided:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_challenge.py $1 $2
```

**If `"success": true`** → go to **Step 2**.  
**If `"success": false, "needs_reasoning": true`** → tell the user this challenge type
requires interactive reasoning; suggest using the botcha-ai skill instead. Stop.  
**If `"success": false`** with `agent_not_registered` or `config_load_failed` → tell
the user to run the botcha-ai skill first. Stop.  
**If `"success": false`** with `rate_limit_exceeded` → tell the user the limit of 100
challenges/hour has been reached for this IP and to try again later. Do not retry. Stop.  
**If `"success": false`** with any other error → go to **Step 2** (failure output).

---

## Step 2: Emit output

**Always emit this JSON block, even on failure.**

### success

```json
{
  "success": true,
  "challenge_type": "speed|compute",
  "time_to_solve_ms": 175,
  "access_token": "...",
  "expires_in": 3600,
  "strategy_notes": "Solved speed challenge in 175ms. Verification credited to agent agent_..."
}
```

### failure

```json
{
  "success": false,
  "challenge_type": "...",
  "error": "...",
  "raw_challenge": "...",
  "raw_verify": "...",
  "strategy_notes": "be specific: what failed and what you tried"
}
```
