# AgentLink Skills

A collection of skills compatible with both [Claude Code](https://claude.ai/code)
and [Hermes Agent](https://hermes-agent.nousresearch.com/). Each skill lives in
its own directory under `skills/` and is defined by a `SKILL.md` file loaded at
runtime.

## Installation

### Claude Code

Add the marketplace and install the skill:

```bash
/plugin marketplace add github:lpezet/agentlink-skills
/plugin install botcha-ai-token@agentlink-skills
```

Or add it once to your project settings (`.claude/settings.json`):

```json
{
  "extraKnownMarketplaces": ["github:lpezet/agentlink-skills"]
}
```

Then install any skill with `/plugin install <skill-name>@agentlink-skills`.

### Hermes Agent

From the command line:

```bash
hermes skills tap add lpezet/agentlink-skills && hermes skills install lpezet/agentlink-skills/botcha-ai-token
```

Or within Hermes:

```bash
/skills tap add lpezet/agentlink-skills
/skills install lpezet/agentlink-skills/botcha-ai-token
/reset
```

## Skills

### [botcha-ai-challenge](skills/botcha-ai-challenge/SKILL.md)

**Category:** auth | **Tags:** auth, botcha.ai, reputation, challenge | **Version:** 1.0.0

Intentionally solve a fresh Botcha.ai challenge to earn reputation. Unlike `botcha-ai-token`
(which uses TAP), this skill always clears the cached token and requests a new challenge,
ensuring the verified event is credited to the registered agent's reputation score. All
challenge types are handled: speed and compute are solved automatically; reasoning and hybrid
questions are answered inline by the LLM.

**Inputs:**

| Parameter  | Required | Description                            |
| ---------- | -------- | -------------------------------------- |
| `app_id`   | yes      | Your Botcha.ai application ID          |
| `audience` | no       | Resource server URL — scopes the token |

**Output:** JSON block with `access_token`, `challenge_type`, `time_to_solve_ms`, and `strategy_notes`.

---

### [botcha-ai-reputation](skills/botcha-ai-reputation/SKILL.md)

**Category:** auth | **Tags:** auth, botcha.ai, reputation, trust | **Version:** 1.0.0

Read a [Botcha.ai](https://botcha.ai) agent's reputation score and event history.
Reputation reflects verified behaviour — it cannot be self-reported. The primary way
to build score today is through the `botcha-ai-token` and `botcha-ai-challenge` skills
(each successful verification contributes a `verification/challenge_solved` event).
The Botcha.ai whitepaper describes a planned reputation marketplace where agents will
earn reputation across partner networks.

**Inputs:**

| Parameter   | Required | Description                                                                                           |
| ----------- | -------- | ----------------------------------------------------------------------------------------------------- |
| `app_id`    | yes      | Your Botcha.ai application ID                                                                         |
| `operation` | yes      | `get` — current score and tier · `list` — event history                                               |
| `category`  | no       | Filter for `list`: `verification`, `attestation`, `delegation`, `session`, `violation`, `endorsement` |
| `limit`     | no       | Max events to return (for `list`)                                                                     |

**Output:** JSON block with `score`, `tier`, and `events` (for `get`), or an array of
event objects (for `list`).

# Testing skills

## Claude

```bash
claude --plugin-dir .
```
