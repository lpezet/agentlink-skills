#!/usr/bin/env python3
"""
Botcha.ai token acquisition — atomic fetch + compute + verify on a single HTTPS connection.
Usage: python3 botcha_get_token.py <app_id> [audience]

For speed/compute challenges: handles everything atomically and prints a result JSON.
For reasoning/hybrid challenges: prints the challenge data with needs_reasoning=true
so the calling agent can answer the questions and submit separately.

Output JSON fields:
  success          bool
  access_token     str   (on success)
  refresh_token    str   (on success)
  expires_in       int   (on success)
  challenge_type   str
  time_to_solve_ms int   (on success)
  needs_reasoning  bool  (true when agent must answer reasoning questions)
  challenge        obj   (present when needs_reasoning=true)
  error            str   (on failure)
  raw_challenge    obj   (on failure)
  raw_verify       obj   (on failure)
  strategy_notes   str
"""
import sys
import hashlib
import json
import http.client
import ssl
import time

if len(sys.argv) < 2:
    print(json.dumps({"success": False, "error": "missing_arg", "strategy_notes": "Usage: python3 botcha_get_token.py <app_id> [audience]"}))
    sys.exit(1)

APP_ID = sys.argv[1]
AUDIENCE = sys.argv[2] if len(sys.argv) > 2 else None
HOST = "api.botcha.ai"

DEBUG_LOG = "/tmp/botcha_debug.log"

def dbg(msg):
    with open(DEBUG_LOG, "a") as f:
        f.write(f"{time.time():.3f} {msg}\n")

conn = None
try:
    dbg(f"START app_id={APP_ID!r}")
    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection(HOST, context=ctx)
    t0 = time.time()

    # Fetch challenge — reuse the connection for verify to avoid a second TLS handshake
    dbg(f"GET /v1/token?app_id={APP_ID}")
    conn.request("GET", f"/v1/token?app_id={APP_ID}")
    r = conn.getresponse()
    body = json.loads(r.read())

    if not body.get("success"):
        print(json.dumps({
            "success": False,
            "challenge_type": "unknown",
            "error": body.get("error", "challenge_fetch_failed"),
            "raw_challenge": body,
            "strategy_notes": "Challenge fetch returned success=false.",
        }))
        sys.exit(0)

    challenge = body["challenge"]
    ctype = body.get("type", "speed")
    cid = challenge["id"]

    if ctype in ("speed", "compute") or ("problems" in challenge and "questions" not in challenge):
        # Pure speed or compute — solve and verify on the same connection
        problems = challenge.get("problems", [])
        answers = [hashlib.sha256(str(p["num"]).encode()).hexdigest()[:8] for p in problems]

        payload_dict = {"id": cid, "answers": answers}
        if AUDIENCE:
            payload_dict["audience"] = AUDIENCE
        payload = json.dumps(payload_dict).encode()

        verify_url = f"/v1/token/verify?app_id={APP_ID}"
        dbg(f"POST {verify_url} payload={payload.decode()[:80]}")
        conn.request(
            "POST",
            verify_url,
            body=payload,
            headers={"Content-Type": "application/json"},
        )
        r2 = conn.getresponse()
        result = json.loads(r2.read())
        elapsed = int((time.time() - t0) * 1000)
        dbg(f"VERIFY result error={result.get('error')} success={result.get('success')} elapsed={elapsed}ms")

        if result.get("success"):
            print(json.dumps({
                "success": True,
                "access_token": result["access_token"],
                "refresh_token": result["refresh_token"],
                "expires_in": result.get("expires_in", 3600),
                "challenge_type": ctype,
                "time_to_solve_ms": result.get("solveTimeMs", elapsed),
                "strategy_notes": f"Solved in {result.get('solveTimeMs', elapsed)}ms via single-connection fetch+compute+verify.",
            }))
        else:
            print(json.dumps({
                "success": False,
                "challenge_type": ctype,
                "error": result.get("error", "verify_failed"),
                "app_id_used": APP_ID,
                "elapsed_ms": elapsed,
                "raw_challenge": challenge,
                "raw_verify": result,
                "strategy_notes": f"Verify failed after {elapsed}ms. app_id_used={APP_ID!r}. Computed answers were: {answers}",
            }))

    else:
        # Reasoning or hybrid — return challenge data; agent must answer questions
        print(json.dumps({
            "success": False,
            "needs_reasoning": True,
            "challenge_type": ctype,
            "challenge": challenge,
            "strategy_notes": (
                f"Challenge type '{ctype}' requires reasoning. "
                "Read challenge.questions, answer inline, then submit via botcha_verify_reasoning.py."
            ),
        }))

except Exception as e:
    print(json.dumps({
        "success": False,
        "error": type(e).__name__,
        "strategy_notes": f"Unhandled exception in botcha_get_token.py: {e}. Check app_id, network, and SSL.",
    }))
finally:
    if conn:
        conn.close()
