#!/usr/bin/env python3
"""
Register an AI agent identity with a Botcha.ai application.
Usage: python3 botcha_register.py <app_id> [--agent-name NAME] [--operator ORG]

Flow:
  1. Load or create ~/.config/botcha-ai/agent.yml (Ed25519 keypair + identity).
  2. If agent_id already exists in config.yml for this app, return it immediately.
  3. Solve a speed challenge (GET /v1/token -> POST /v1/token/verify) to get a JWT.
  4. POST /v1/agents/register with the JWT Bearer -> agent_id.
  5. POST /v1/agents/register/tap with the JWT Bearer, agent_id, and raw 32-byte
     Ed25519 public key in base64 (NOT PEM format).
  6. Save agent_id to ~/.config/botcha-ai/config.yml.

Output JSON fields:
  success     bool
  agent_id    str   — the agent's ID for this app
  registered  bool  — true if a new registration was performed this run
  missing     list  — when agent_name/operator are needed; re-run with flags
  error       str   — on failure
  raw_response obj  — on API failure
"""
import sys
import json
import argparse
import pathlib
import os
import http.client
import ssl
import hashlib
import base64

try:
    import yaml
except ImportError:
    print(json.dumps({"success": False, "error": "pyyaml not installed. Run: pip install pyyaml"}))
    sys.exit(1)

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat, PrivateFormat, NoEncryption, load_pem_public_key,
    )
except ImportError:
    print(json.dumps({"success": False, "error": "cryptography not installed. Run: pip install cryptography"}))
    sys.exit(1)

parser = argparse.ArgumentParser()
parser.add_argument("app_id")
parser.add_argument("--agent-name", dest="agent_name", default=None)
parser.add_argument("--operator", dest="operator", default=None)
args = parser.parse_args()

CFG_DIR    = pathlib.Path.home() / ".config" / "botcha-ai"
AGENT_FILE = CFG_DIR / "agent.yml"
CFG_FILE   = CFG_DIR / "config.yml"
HOST       = "api.botcha.ai"

# ── Step 1: agent.yml — load or create identity + keypair ────────────────────

agent_data = (yaml.safe_load(AGENT_FILE.read_text()) if AGENT_FILE.exists() else None) or {}

if args.agent_name:
    agent_data["agent_name"] = args.agent_name
if args.operator:
    agent_data["operator"] = args.operator

missing = [f for f in ("agent_name", "operator") if not agent_data.get(f)]
if missing:
    print(json.dumps({
        "success": False,
        "missing": missing,
        "hint": "Re-run with: --agent-name NAME --operator ORG",
    }))
    sys.exit(0)

agent_data.setdefault("trust_level", "verified")

if not agent_data.get("private_key_pem"):
    priv = Ed25519PrivateKey.generate()
    pub  = priv.public_key()
    agent_data["public_key_pem"]  = pub.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
    agent_data["private_key_pem"] = priv.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()

CFG_DIR.mkdir(parents=True, exist_ok=True)
AGENT_FILE.write_text(yaml.dump(agent_data, default_flow_style=False))
os.chmod(AGENT_FILE, 0o600)

# ── Step 2: config.yml — check for existing agent_id ─────────────────────────

cfg_data = (yaml.safe_load(CFG_FILE.read_text()) if CFG_FILE.exists() else None) or {}
cfg_data.setdefault("apps", {})

agent_id = cfg_data["apps"].get(args.app_id, {}).get("agent_id")
if agent_id:
    print(json.dumps({"success": True, "agent_id": agent_id, "registered": False}))
    sys.exit(0)

# ── Step 3: solve speed challenge to get JWT ──────────────────────────────────

ctx = ssl.create_default_context()

c = http.client.HTTPSConnection(HOST, context=ctx)
c.request("GET", f"/v1/token?app_id={args.app_id}")
challenge_resp = json.loads(c.getresponse().read().decode())

if not challenge_resp.get("success"):
    print(json.dumps({
        "success": False,
        "error": "challenge_fetch_failed",
        "raw_response": challenge_resp,
    }))
    sys.exit(0)

challenge = challenge_resp["challenge"]
cid       = challenge["id"]
problems  = challenge.get("problems", [])
answers   = [hashlib.sha256(str(p["num"]).encode()).hexdigest()[:8] for p in problems]

verify_payload = json.dumps({"id": cid, "answers": answers, "agent_id": agent_id or ""}).encode()
c.request(
    "POST", f"/v1/token/verify?app_id={args.app_id}",
    body=verify_payload,
    headers={"Content-Type": "application/json"},
)
token_resp = json.loads(c.getresponse().read().decode())
c.close()

jwt = token_resp.get("access_token")
if not jwt:
    print(json.dumps({
        "success": False,
        "error": "challenge_solve_failed",
        "raw_response": token_resp,
    }))
    sys.exit(0)

# ── Step 4: register agent identity → agent_id ───────────────────────────────

reg_payload = json.dumps({
    "name":     agent_data["agent_name"],
    "operator": agent_data["operator"],
    "version":  "1.0.0",
    "app_id":   args.app_id,
}).encode()

c = http.client.HTTPSConnection(HOST, context=ctx)
c.request(
    "POST", f"/v1/agents/register?app_id={args.app_id}",
    body=reg_payload,
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {jwt}"},
)
reg_resp = json.loads(c.getresponse().read().decode())
c.close()

agent_id = reg_resp.get("agent_id") or reg_resp.get("id")
if not agent_id:
    print(json.dumps({
        "success": False,
        "error": "agent_registration_failed",
        "raw_response": reg_resp,
    }))
    sys.exit(0)

# ── Step 5: register TAP keypair — raw 32-byte Ed25519 pubkey in base64 ──────

raw_pubkey_b64 = base64.b64encode(
    load_pem_public_key(agent_data["public_key_pem"].encode()).public_bytes(Encoding.Raw, PublicFormat.Raw)
).decode()

tap_payload = json.dumps({
    "agent_id":            agent_id,
    "name":                agent_data["agent_name"],
    "public_key":          raw_pubkey_b64,
    "signature_algorithm": "ed25519",
    "capabilities":        [{"action": "browse"}, {"action": "search"}],
}).encode()

c = http.client.HTTPSConnection(HOST, context=ctx)
c.request(
    "POST", f"/v1/agents/register/tap?app_id={args.app_id}",
    body=tap_payload,
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {jwt}"},
)
tap_resp = json.loads(c.getresponse().read().decode())
c.close()

if not (tap_resp.get("success") or tap_resp.get("tap_enabled")):
    print(json.dumps({
        "success": False,
        "error": "tap_registration_failed",
        "raw_response": tap_resp,
    }))
    sys.exit(0)

# ── Step 6: persist agent_id to config.yml ────────────────────────────────────

cfg_data["apps"][args.app_id] = {
    **cfg_data["apps"].get(args.app_id, {}),
    "agent_id":      agent_id,
}
CFG_FILE.write_text(yaml.dump(cfg_data, default_flow_style=False))
os.chmod(CFG_FILE, 0o600)

print(json.dumps({"success": True, "agent_id": agent_id, "registered": True}))
