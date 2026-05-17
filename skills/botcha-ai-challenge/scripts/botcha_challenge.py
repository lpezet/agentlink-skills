#!/usr/bin/env python3
"""
Solve a fresh Botcha.ai challenge to earn reputation through verified challenge-solving.

Unlike botcha_get_token.py (which solves challenges as a last-resort fallback), this
script intentionally clears any cached token first so a fresh challenge is always
solved and the resulting verification event is attributed to the registered agent.

Usage: python3 botcha_challenge.py <app_id> [audience]

Rate limit: 100 challenges per hour per IP. Do not call in a loop.

Reads agent_id from ~/.config/botcha-ai/config.yml (agent must already be registered
via the botcha-ai skill). Clears cached access_token/expires_at/token_type before
requesting the challenge. Saves the resulting token back to config.yml with
token_type="challenge".

Speed and compute challenges are solved automatically. Reasoning and hybrid challenges
return needs_reasoning=true with challenge_id and challenge payload for the calling
skill to answer interactively before calling botcha_verify_reasoning.py.

Output JSON fields:
  success          bool
  access_token     str   (on success, auto-solved)
  refresh_token    str   (on success, auto-solved)
  expires_in       int   (on success, auto-solved)
  challenge_type   str
  time_to_solve_ms int   (on success, auto-solved)
  needs_reasoning  bool  (true for reasoning/hybrid — skill must answer interactively)
  challenge_id     str   (present when needs_reasoning=true)
  challenge        dict  (present when needs_reasoning=true — contains questions array)
  error            str   (on failure)
  strategy_notes   str
"""
import sys
import hashlib
import json
import http.client
import ssl
import time
import pathlib

try:
    import yaml
except ImportError:
    print(json.dumps({"success": False, "error": "pyyaml not installed. Run: pip install pyyaml", "strategy_notes": ""}))
    sys.exit(1)

if len(sys.argv) < 2:
    print(json.dumps({"success": False, "error": "missing_arg", "strategy_notes": "Usage: python3 botcha_challenge.py <app_id> [audience]"}))
    sys.exit(1)

APP_ID   = sys.argv[1]
AUDIENCE = sys.argv[2] if len(sys.argv) > 2 else None
HOST     = "api.botcha.ai"
CFG_FILE = pathlib.Path.home() / ".config" / "botcha-ai" / "config.yml"

try:
    cfg_data = yaml.safe_load(CFG_FILE.read_text())
    AGENT_ID = cfg_data["apps"][APP_ID].get("agent_id")
except Exception as e:
    print(json.dumps({
        "success": False,
        "error": f"config_load_failed: {e}",
        "strategy_notes": "Run /botcha-ai-agent first.",
    }))
    sys.exit(1)

if not AGENT_ID:
    print(json.dumps({
        "success": False,
        "error": "agent_not_registered",
        "strategy_notes": "No agent_id found for this app. Run /botcha-ai-agent first.",
    }))
    sys.exit(1)

# Always clear cached token — the whole point is to earn a fresh verification event.
for key in ("access_token", "expires_at", "token_type"):
    cfg_data["apps"][APP_ID].pop(key, None)
CFG_FILE.write_text(yaml.dump(cfg_data, default_flow_style=False))

ctx  = ssl.create_default_context()
conn = None

try:
    conn = http.client.HTTPSConnection(HOST, context=ctx)
    t0   = time.time()

    conn.request("GET", f"/v1/token?app_id={APP_ID}")
    r    = conn.getresponse()
    body = json.loads(r.read())

    if not body.get("success"):
        error = body.get("error", "challenge_fetch_failed")
        notes = ("Rate limit of 100 challenges/hour/IP reached. Try again later."
                 if error == "rate_limit_exceeded"
                 else "Challenge fetch returned success=false.")
        print(json.dumps({
            "success":        False,
            "challenge_type": "unknown",
            "error":          error,
            "raw_challenge":  body,
            "strategy_notes": notes,
        }))
        sys.exit(0)

    challenge = body["challenge"]
    ctype     = body.get("type", "speed")
    cid       = challenge["id"]

    if ctype in ("speed", "compute") or ("problems" in challenge and "questions" not in challenge):
        problems = challenge.get("problems", [])
        answers  = [hashlib.sha256(str(p["num"]).encode()).hexdigest()[:8] for p in problems]

        payload_dict = {"id": cid, "answers": answers, "agent_id": AGENT_ID}
        if AUDIENCE:
            payload_dict["audience"] = AUDIENCE

        conn.request("POST", f"/v1/token/verify?app_id={APP_ID}",
                     body=json.dumps(payload_dict).encode(),
                     headers={"Content-Type": "application/json"})
        r2      = conn.getresponse()
        result  = json.loads(r2.read())
        elapsed = int((time.time() - t0) * 1000)

        if result.get("success"):
            expires_in = result.get("expires_in", 3600)
            cfg_data["apps"][APP_ID]["access_token"] = result["access_token"]
            cfg_data["apps"][APP_ID]["expires_at"]   = time.time() + expires_in
            cfg_data["apps"][APP_ID]["token_type"]   = "challenge"
            CFG_FILE.write_text(yaml.dump(cfg_data, default_flow_style=False))
            print(json.dumps({
                "success":          True,
                "access_token":     result["access_token"],
                "refresh_token":    result.get("refresh_token"),
                "expires_in":       expires_in,
                "challenge_type":   ctype,
                "time_to_solve_ms": result.get("solveTimeMs", elapsed),
                "strategy_notes":   f"Solved {ctype} challenge in {result.get('solveTimeMs', elapsed)}ms. Verification credited to agent {AGENT_ID}.",
            }))
        else:
            print(json.dumps({
                "success":        False,
                "challenge_type": ctype,
                "error":          result.get("error", "verify_failed"),
                "raw_challenge":  challenge,
                "raw_verify":     result,
                "strategy_notes": f"Verify failed after {elapsed}ms.",
            }))

    else:
        # Reasoning/hybrid: return challenge data for the skill to handle interactively.
        print(json.dumps({
            "success":         False,
            "needs_reasoning": True,
            "challenge_type":  ctype,
            "challenge_id":    cid,
            "challenge":       challenge,
            "strategy_notes":  f"Challenge type '{ctype}' requires reasoning answers.",
        }))

except Exception as e:
    print(json.dumps({
        "success":        False,
        "error":          type(e).__name__,
        "strategy_notes": f"Unhandled exception: {e}",
    }))
finally:
    if conn:
        conn.close()
