---
name: botcha-ai-challenge
description: |
  Intentionally solve a Botcha.ai challenge to earn reputation through verified
  challenge-solving. Unlike botcha-ai-token (which uses TAP), this skill explicitly
  requests and solves a fresh challenge — clearing any cached token first — so the
  verified event is always credited to the registered agent's reputation score.

  All challenge types are handled:
    - Speed and compute: solved automatically by script.
    - Reasoning and hybrid: questions are returned and answered inline by the LLM,
      then submitted via botcha_verify_reasoning.py.

  Prerequisite: the agent must already be registered via /botcha-ai-agent
  (identity in ~/.config/botcha-ai/agent.yml and config.yml).

  Call with:
    app_id:   <Botcha.ai app ID>    [required]
    audience: <resource server URL> [optional]

  Returns a JSON block — see Step 3.
context: fork
allowed-tools: Bash(python3 *)
arguments:
  - app_id
  - audience
argument-hint: "<app_id> [<audience>]"
version: 1.0.0
author: lpezet@gmail.com
metadata:
  hermes:
    tags: [auth, botcha.ai, reputation, challenge]
    category: auth
---

Your sole job: solve a fresh Botcha.ai challenge to earn a reputation event and return
the result as a JSON block.

Parameters: `$app_id` (required), `$audience` (optional).

Config dir: `~/.config/botcha-ai/`  
Scripts: `${CLAUDE_SKILL_DIR}/scripts/`

## CRITICAL RULES

1. **NEVER use curl** — use the pre-built script for all API calls.
2. The `private_key_pem` in `agent.yml` is sensitive. Never log or emit it.
3. If config files are missing or `agent_not_registered` is returned, tell the user
   to run **/botcha-ai-agent $app_id** first. Stop.
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

TAP challenge-response (via botcha-ai-token) is a stronger trust signal, but
this skill is useful for proactively accumulating verification events between TAP auths.

---

## Step 1: Solve the challenge

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_challenge.py $app_id
```

Include `$audience` if one was provided:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_challenge.py $app_id $audience
```

**If `"success": true`** → go to **Step 3**.  
**If `"success": false, "needs_reasoning": true`** → go to **Step 2**.  
**If `"success": false`** with `agent_not_registered` or `config_load_failed` → tell
the user to run **/botcha-ai-agent $app_id** first. Stop.  
**If `"success": false`** with `rate_limit_exceeded` → tell the user the limit of 100
challenges/hour has been reached for this IP and to try again later. Do not retry. Stop.  
**If `"success": false`** with any other error → go to **Step 3** (failure output).

---

## Step 2: Answer reasoning questions (only when needs_reasoning: true)

The script output contains a `challenge` object with a `questions` array and a
`challenge_id`. You have **30 seconds** from challenge issuance — work quickly.

For each question read the `id` and build `{"<question_id>": "<answer>", ...}`.

**By category:**

- **Analogy** (`A is to B as C is to ?`): identify the A→B relationship, apply to C.
- **Math / word problem**: extract the numbers and compute directly.
- **Logic** (if/then, ordering, set membership): trace the conditions step by step.
- **Wordplay** (anagram, rhyme, letter pattern): work through it character by character.
- **Computer science** (complexity, data structures, algorithms): apply knowledge directly.
- **Pattern completion** (number or symbol sequences): find the rule, apply it.

If you see a category not listed, best-guess the answer and record the category
name in `strategy_notes` so the instructions can be extended.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_verify_reasoning.py $app_id CHALLENGE_ID TYPE '{"q-id-1":"answer1"}'
```

For hybrid challenges, the answers JSON must be:

```json
{"speed_answers": [...], "reasoning_answers": {"q-id": "answer"}}
```

**If `"success": true`** → go to **Step 3**.  
**If `"success": false`** → go to **Step 3** (failure output).

---

## Step 3: Emit output

**Always emit this JSON block, even on failure.**

### success

```json
{
  "success": true,
  "challenge_type": "speed|compute|reasoning|hybrid",
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
