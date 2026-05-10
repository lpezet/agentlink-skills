# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A collection of LLM skills compatible with Claude Code and Hermes Agent. Each skill is a directory under `skills/` containing a `SKILL.md` (the LLM instructions) and an optional `scripts/` subdirectory of Python helpers.

## Registering a skill

`.claude-plugin/marketplace.json` is the Claude Code plugin manifest. When adding a new skill, add an entry to the `plugins` array:

```json
{
  "name": "skill-name",
  "source": "./skills",
  "strict": false,
  "skills": "skill-name"
}
```

The `skills` field must match the skill's directory name (and its `name` frontmatter field).

## SKILL.md structure

The frontmatter fields that matter:

| Field                      | Purpose                                                        |
| -------------------------- | -------------------------------------------------------------- |
| `name`                     | Must match the directory name                                  |
| `allowed-tools`            | Whitelist of tools the skill may call, e.g. `Bash(python3 *)`  |
| `arguments`                | Positional args the skill accepts — used by Hermes for routing |
| `metadata.hermes.category` | Used for discovery/filtering in Hermes                         |

Reference scripts in the body as `${CLAUDE_SKILL_DIR}/scripts/<script>.py` — the runtime resolves this to the skill's directory at invocation time.

## Script conventions

All scripts in `scripts/` follow the same contract:

- Output exactly one JSON object to stdout. Never print progress lines or partial output.
- Always include `"success": bool` in every output path (success and failure).
- Include `"strategy_notes"` on failure — this is the primary debugging signal.
- Include `"raw_response"` on API failure so the calling agent can inspect the server reply.
- Dependencies: stdlib only, plus `pyyaml` and `cryptography`. No other packages.
- Use `sys.exit(0)` for handled failures (bad API response), `sys.exit(1)` only for usage errors.

## botcha-ai skill family

Three skills share config at `~/.config/botcha-ai/` (both files chmod 600):

- `agent.yml` — Ed25519 keypair + `agent_name` / `operator` (shared across all apps)
- `config.yml` — per-app data keyed by `app_id`:
  - `agent_id` — registered agent identifier
  - `refresh_token` — long-lived token for the fast-refresh path
  - `access_token` — cached Bearer token
  - `expires_at` — Unix timestamp of token expiry (stored so JWT decoding is never needed)
  - `token_type` — `"tap"` or `"challenge"` (how the cached token was obtained)

### botcha-ai auth precedence

1. **Force reset** (when `$3 == "force"`) — `botcha_token_clear.py` wipes `access_token`, `expires_at`, `token_type`, and `refresh_token`, then falls through to TAP
2. **Refresh token** — `POST /v1/token/refresh` if a stored `refresh_token` exists
3. **TAP** (`botcha_tap_auth.py`) — Ed25519 nonce-sign via `POST /v1/agents/auth` → `POST /v1/agents/auth/verify`
4. **Challenge fallback** (`botcha_get_token.py`) — speed/compute solved atomically on one HTTPS connection; reasoning/hybrid returns `needs_reasoning: true` for the agent to answer inline via `botcha_verify_reasoning.py`

### botcha-ai-reputation auth

The reputation scripts (`botcha_reputation_get.py`, `botcha_reputation_events.py`) manage auth
inline — they do not call into `botcha-ai` scripts. Precedence:

1. **Cached token** — reused if `expires_at` is more than 60 s away
2. **TAP** — inline challenge-response using the stored Ed25519 key
3. **Speed-challenge fallback** — inline solve; `agent_id` is always included in the verify payload so the event is credited to reputation

After any fresh auth the token, expiry, and type are written back to `config.yml`.

### botcha-ai-challenge

Always clears the cached token and solves a fresh speed/compute challenge with `agent_id`
in the verify payload, so the event is explicitly credited to the agent's reputation.
Reasoning/hybrid challenges are not handled — use `botcha-ai` for those.

**Rate limit: 100 challenges per hour per IP.** Never call this skill in a loop or in
rapid succession. On a `rate_limit_exceeded` error, stop and inform the user.

### Challenge verify payloads

All scripts that call `/v1/token/verify` or `/v1/challenges/*/verify` include `"agent_id"`
in the request body so solved challenges are attributed to the registered agent for reputation.

Every API request to `api.botcha.ai` must include `?app_id=<app_id>` as a query parameter.
