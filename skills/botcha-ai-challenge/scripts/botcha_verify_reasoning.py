#!/usr/bin/env python3
"""
Submit reasoning (or hybrid) answers to Botcha.ai and save the resulting token.
Usage: python3 botcha_verify_reasoning.py <app_id> <challenge_id> <challenge_type> <answers_json> [audience]

  challenge_type  "reasoning" | "standard" | "hybrid"
  answers_json    For reasoning/standard: '{"q-id-1": "answer1", "q-id-2": "answer2"}'
                  For hybrid: '{"speed_answers": [...], "reasoning_answers": {...}}'

Output: same JSON envelope as botcha_challenge.py
"""
import sys
import json
import http.client
import ssl
import time
import pathlib

APP_ID        = sys.argv[1]
CHALLENGE_ID  = sys.argv[2]
CHALLENGE_TYPE = sys.argv[3]
ANSWERS       = json.loads(sys.argv[4])
AUDIENCE      = sys.argv[5] if len(sys.argv) > 5 else None

HOST     = "api.botcha.ai"
CFG_FILE = pathlib.Path.home() / ".config" / "botcha-ai" / "config.yml"

try:
    import yaml
except ImportError:
    print(json.dumps({"success": False, "error": "pyyaml not installed. Run: pip install pyyaml", "strategy_notes": ""}))
    sys.exit(1)

try:
    cfg_data = yaml.safe_load(CFG_FILE.read_text())
    AGENT_ID = cfg_data["apps"][APP_ID].get("agent_id")
except Exception as e:
    print(json.dumps({"success": False, "error": f"config_load_failed: {e}", "strategy_notes": ""}))
    sys.exit(1)

ctx  = ssl.create_default_context()
conn = http.client.HTTPSConnection(HOST, context=ctx)

try:
    t0 = time.time()

    if CHALLENGE_TYPE == "hybrid":
        payload_dict = {
            "type":              "hybrid",
            "speed_answers":     ANSWERS["speed_answers"],
            "reasoning_answers": ANSWERS["reasoning_answers"],
        }
        path = f"/v1/challenges/{CHALLENGE_ID}/verify?app_id={APP_ID}"
    else:
        payload_dict = {"id": CHALLENGE_ID, "answers": ANSWERS}
        path = f"/v1/token/verify?app_id={APP_ID}"

    if AGENT_ID:
        payload_dict["agent_id"] = AGENT_ID
    if AUDIENCE:
        payload_dict["audience"] = AUDIENCE

    payload = json.dumps(payload_dict).encode()
    conn.request("POST", path, body=payload, headers={"Content-Type": "application/json"})
    r      = conn.getresponse()
    result = json.loads(r.read())
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
            "challenge_type":   CHALLENGE_TYPE,
            "time_to_solve_ms": result.get("solveTimeMs", elapsed),
            "strategy_notes":   f"Reasoning submitted and verified in {result.get('solveTimeMs', elapsed)}ms. Verification credited to agent {AGENT_ID}.",
        }))
    else:
        print(json.dumps({
            "success":        False,
            "challenge_type": CHALLENGE_TYPE,
            "error":          result.get("error", "verify_failed"),
            "raw_verify":     result,
            "strategy_notes": "Reasoning verify failed. Check answers format and question IDs.",
        }))

finally:
    conn.close()
