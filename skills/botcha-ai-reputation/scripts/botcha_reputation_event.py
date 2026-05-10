#!/usr/bin/env python3
"""
Record a reputation event for the registered agent.
Usage: python3 botcha_reputation_event.py <app_id> <category> <action> [metadata_json]

Authenticates via TAP keypair (falls back to speed challenge) to obtain a Bearer token.
Reads identity from ~/.config/botcha-ai/agent.yml and config.yml.

Categories: verification, attestation, delegation, session, violation, endorsement
Actions:    challenge_solved, challenge_failed, auth_success, auth_failure,
            attestation_issued, attestation_verified, attestation_revoked,
            delegation_granted, delegation_received, delegation_revoked,
            session_created, session_expired, session_terminated,
            rate_limit_exceeded, invalid_token, abuse_detected,
            endorsement_received, endorsement_given

metadata_json example: '{"transaction_amount": 42.50}'

Output JSON fields:
  success   bool
  event_id  str   (on success)
  score     int   updated score after event (on success)
  error     str   (on failure)
  raw_response obj (on failure)
"""
import sys
import json
import pathlib
import http.client
import ssl
import base64
import hashlib

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

if len(sys.argv) < 4:
    print(json.dumps({
        "success": False,
        "error": "Usage: botcha_reputation_event.py <app_id> <category> <action> [metadata_json]",
    }))
    sys.exit(1)

APP_ID   = sys.argv[1]
CATEGORY = sys.argv[2]
ACTION   = sys.argv[3]
try:
    METADATA = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
except json.JSONDecodeError as e:
    print(json.dumps({"success": False, "error": f"invalid metadata_json: {e}"}))
    sys.exit(1)

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
        "hint": "Run botcha_setup.py (botcha-ai skill) first.",
    }))
    sys.exit(1)

ctx = ssl.create_default_context()

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
        json.dumps({"id": cid, "answers": answers}).encode(),
        {"Content-Type": "application/json"},
    )
    token_resp = json.loads(c.getresponse().read().decode())
    c.close()
    return token_resp.get("access_token"), token_resp

try:
    jwt, raw = tap_auth()
    if not jwt:
        jwt, raw = speed_challenge_auth()
    if not jwt:
        print(json.dumps({"success": False, "error": "auth_failed", "raw_response": raw}))
        sys.exit(0)

    payload = json.dumps({
        "agent_id": agent_id,
        "category": CATEGORY,
        "action":   ACTION,
        "metadata": METADATA,
    }).encode()

    c = http.client.HTTPSConnection(HOST, context=ctx)
    c.request(
        "POST", f"/v1/reputation/events?app_id={APP_ID}",
        body=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {jwt}"},
    )
    resp = json.loads(c.getresponse().read().decode())
    c.close()

    if resp.get("error"):
        print(json.dumps({"success": False, "error": resp["error"], "raw_response": resp}))
    else:
        print(json.dumps({
            "success":  True,
            "event_id": resp.get("event_id") or resp.get("id"),
            "score":    resp.get("score"),
        }))
except Exception as e:
    print(json.dumps({"success": False, "error": type(e).__name__, "detail": str(e)}))
