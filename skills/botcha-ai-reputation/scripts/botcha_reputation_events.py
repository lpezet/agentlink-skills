#!/usr/bin/env python3
"""
List reputation events for the registered agent.
Usage: python3 botcha_reputation_events.py <app_id> [category] [limit]

Reads agent_id from ~/.config/botcha-ai/config.yml.
Auth is self-managed: cached token (tap or challenge) is reused if still valid;
otherwise TAP challenge-response is attempted first, with puzzle-solving as fallback.
The resulting token, its expiry, and type are written back to config.yml.

category: verification | attestation | delegation | session | violation | endorsement
limit:    integer (default: server default, typically 20)

Output JSON fields:
  success   bool
  agent_id  str
  events    list of event objects
  error     str  (on failure)
  raw_response obj (on failure)
"""
import sys
import json
import pathlib
import http.client
import ssl
import base64
import hashlib
import time

try:
    import yaml
except ImportError:
    print(json.dumps({"success": False, "error": "pyyaml not installed. Run: pip install pyyaml"}))
    sys.exit(1)

try:
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
except ImportError:
    print(json.dumps({"success": False, "error": "cryptography not installed. Run: pip install cryptography"}))
    sys.exit(1)

if len(sys.argv) < 2:
    print(json.dumps({"success": False, "error": "Usage: botcha_reputation_events.py <app_id> [category] [limit]"}))
    sys.exit(1)

APP_ID     = sys.argv[1]
CATEGORY   = sys.argv[2] if len(sys.argv) > 2 else None
LIMIT      = sys.argv[3] if len(sys.argv) > 3 else None

CFG_DIR    = pathlib.Path.home() / ".config" / "botcha-ai"
AGENT_FILE = CFG_DIR / "agent.yml"
CFG_FILE   = CFG_DIR / "config.yml"
HOST       = "api.botcha.ai"

try:
    agent_data = yaml.safe_load(AGENT_FILE.read_text())
    cfg_data   = yaml.safe_load(CFG_FILE.read_text())
    agent_id   = cfg_data["apps"][APP_ID]["agent_id"]
    priv       = load_pem_private_key(agent_data["private_key_pem"].encode(), password=None)
except Exception as e:
    print(json.dumps({
        "success": False,
        "error": f"config_load_failed: {e}",
        "hint": "Run /botcha-ai-agent first.",
    }))
    sys.exit(1)

ctx = ssl.create_default_context()

def get_cached_token():
    token      = cfg_data["apps"][APP_ID].get("access_token")
    expires_at = cfg_data["apps"][APP_ID].get("expires_at", 0)
    if token and time.time() < expires_at - 60:
        return token
    return None

def save_token(token, expires_in, token_type):
    cfg_data["apps"][APP_ID]["access_token"] = token
    cfg_data["apps"][APP_ID]["expires_at"]   = time.time() + expires_in
    cfg_data["apps"][APP_ID]["token_type"]   = token_type
    CFG_FILE.write_text(yaml.dump(cfg_data, default_flow_style=False))

def tap_auth():
    c = http.client.HTTPSConnection(HOST, context=ctx)
    c.request(
        "POST", f"/v1/agents/auth?app_id={APP_ID}",
        json.dumps({"agent_id": agent_id, "app_id": APP_ID}).encode(),
        {"Content-Type": "application/json"},
    )
    nonce_resp   = json.loads(c.getresponse().read().decode())
    challenge_id = nonce_resp.get("challenge_id")
    nonce        = nonce_resp.get("nonce")
    c.close()
    if not challenge_id or not nonce:
        return None, nonce_resp
    sig = base64.b64encode(priv.sign(nonce.encode())).decode()
    c = http.client.HTTPSConnection(HOST, context=ctx)
    c.request(
        "POST", f"/v1/agents/auth/verify?app_id={APP_ID}",
        json.dumps({"challenge_id": challenge_id, "agent_id": agent_id, "signature": sig}).encode(),
        {"Content-Type": "application/json"},
    )
    token_resp = json.loads(c.getresponse().read().decode())
    c.close()
    return token_resp.get("access_token"), token_resp

def speed_challenge_auth():
    c = http.client.HTTPSConnection(HOST, context=ctx)
    c.request("GET", f"/v1/token?app_id={APP_ID}")
    challenge_resp = json.loads(c.getresponse().read().decode())
    c.close()
    if not challenge_resp.get("success"):
        return None, challenge_resp
    challenge = challenge_resp["challenge"]
    cid       = challenge["id"]
    problems  = challenge.get("problems", [])
    answers   = [hashlib.sha256(str(p["num"]).encode()).hexdigest()[:8] for p in problems]
    c = http.client.HTTPSConnection(HOST, context=ctx)
    c.request(
        "POST", f"/v1/token/verify?app_id={APP_ID}",
        json.dumps({"id": cid, "answers": answers, "agent_id": agent_id}).encode(),
        {"Content-Type": "application/json"},
    )
    token_resp = json.loads(c.getresponse().read().decode())
    c.close()
    return token_resp.get("access_token"), token_resp

params = f"app_id={APP_ID}"
if CATEGORY:
    params += f"&category={CATEGORY}"
if LIMIT:
    params += f"&limit={LIMIT}"

try:
    raw = {}
    jwt = get_cached_token()
    if not jwt:
        jwt, raw = tap_auth()
        if jwt:
            save_token(jwt, raw.get("expires_in", 3600), "tap")
    if not jwt:
        jwt, raw = speed_challenge_auth()
        if jwt:
            save_token(jwt, raw.get("expires_in", 3600), "challenge")
    if not jwt:
        print(json.dumps({"success": False, "error": "auth_failed", "raw_response": raw}))
        sys.exit(0)

    c = http.client.HTTPSConnection(HOST, context=ctx)
    c.request("GET", f"/v1/reputation/{agent_id}/events?{params}",
              headers={"Authorization": f"Bearer {jwt}"})
    resp = json.loads(c.getresponse().read().decode())
    c.close()

    if resp.get("error"):
        print(json.dumps({"success": False, "error": resp["error"], "raw_response": resp}))
    else:
        events = resp.get("events") or resp.get("data") or []
        print(json.dumps({"success": True, "agent_id": agent_id, "events": events}))
except Exception as e:
    print(json.dumps({"success": False, "error": type(e).__name__, "detail": str(e)}))
