#!/usr/bin/env python3
"""
Obtain a Botcha.ai JWT for a registered TAP agent.
Usage: python3 botcha_token.py <app_id> [--audience URL] [--force]

Auth precedence:
  1. Cached access_token (returned immediately if expires_at > now + 60s) — skipped with --force
  2. Refresh token (POST /v1/token/refresh) — skipped with --force
  3. TAP challenge-response (POST /v1/agents/auth + /v1/agents/auth/verify)

Requires ~/.config/botcha-ai/agent.yml (Ed25519 keypair)
     and ~/.config/botcha-ai/config.yml (agent_id for app_id).
Run /botcha-ai-agent first if agent_id is missing.

Output JSON fields:
  success        bool
  access_token   str   (on success)
  refresh_token  str   (on success)
  expires_in     int   (on success)
  auth_method    str   "cached" | "refresh" | "tap"
  error          str   (on failure)
  raw_response   obj   (on failure)
  strategy_notes str
"""
import sys
import json
import argparse
import pathlib
import http.client
import ssl
import base64
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

parser = argparse.ArgumentParser()
parser.add_argument("app_id")
parser.add_argument("--audience", default=None)
parser.add_argument("--force", action="store_true")
args = parser.parse_args()

CFG_DIR    = pathlib.Path.home() / ".config" / "botcha-ai"
AGENT_FILE = CFG_DIR / "agent.yml"
CFG_FILE   = CFG_DIR / "config.yml"
HOST       = "api.botcha.ai"

try:
    agent_data = yaml.safe_load(AGENT_FILE.read_text())
    cfg_data   = (yaml.safe_load(CFG_FILE.read_text()) if CFG_FILE.exists() else None) or {}
    app_cfg    = cfg_data.get("apps", {}).get(args.app_id)
    if not app_cfg:
        raise KeyError(f"app_id {args.app_id!r} not found in config.yml")
    agent_id = app_cfg.get("agent_id")
    if not agent_id:
        raise KeyError(f"no agent_id for {args.app_id!r} — run /botcha-ai-agent first")
    priv = load_pem_private_key(agent_data["private_key_pem"].encode(), password=None)
except Exception as e:
    print(json.dumps({
        "success": False,
        "error": f"config_load_failed: {e}",
        "strategy_notes": "Run /botcha-ai-agent to register an agent identity first.",
    }))
    sys.exit(1)

def emit_success(access_token, refresh_token, expires_in, auth_method):
    app_cfg["access_token"]  = access_token
    app_cfg["refresh_token"] = refresh_token or app_cfg.get("refresh_token", "")
    app_cfg["expires_at"]    = time.time() + expires_in
    app_cfg["token_type"]    = "tap"
    cfg_data["apps"][args.app_id] = app_cfg
    CFG_FILE.write_text(yaml.dump(cfg_data, default_flow_style=False))
    print(json.dumps({
        "success":        True,
        "access_token":   access_token,
        "refresh_token":  app_cfg["refresh_token"],
        "expires_in":     expires_in,
        "auth_method":    auth_method,
        "strategy_notes": f"Auth via {auth_method}.",
    }))

ctx = ssl.create_default_context()

# ── 1. Cached token ───────────────────────────────────────────────────────────

if not args.force:
    cached     = app_cfg.get("access_token")
    expires_at = app_cfg.get("expires_at", 0)
    if cached and time.time() < expires_at - 60:
        print(json.dumps({
            "success":        True,
            "access_token":   cached,
            "refresh_token":  app_cfg.get("refresh_token", ""),
            "expires_in":     int(expires_at - time.time()),
            "auth_method":    "cached",
            "strategy_notes": "Returned valid cached access_token.",
        }))
        sys.exit(0)

# ── 2. Refresh token ──────────────────────────────────────────────────────────

if not args.force:
    stored_refresh = app_cfg.get("refresh_token")
    if stored_refresh:
        try:
            c = http.client.HTTPSConnection(HOST, context=ctx)
            c.request(
                "POST", f"/v1/token/refresh?app_id={args.app_id}",
                json.dumps({"refresh_token": stored_refresh}).encode(),
                {"Content-Type": "application/json"},
            )
            resp         = json.loads(c.getresponse().read().decode())
            access_token = resp.get("access_token")
            c.close()
            if access_token:
                emit_success(access_token, resp.get("refresh_token", stored_refresh), resp.get("expires_in", 3600), "refresh")
                sys.exit(0)
            # stale refresh token — fall through to TAP
            app_cfg["refresh_token"] = ""
        except Exception:
            pass

# ── 3. TAP challenge-response ─────────────────────────────────────────────────

try:
    c = http.client.HTTPSConnection(HOST, context=ctx)
    c.request(
        "POST", f"/v1/agents/auth?app_id={args.app_id}",
        json.dumps({"agent_id": agent_id, "app_id": args.app_id}).encode(),
        {"Content-Type": "application/json"},
    )
    nonce_resp   = json.loads(c.getresponse().read().decode())
    challenge_id = nonce_resp.get("challenge_id")
    nonce        = nonce_resp.get("nonce")
    c.close()

    if not challenge_id or not nonce:
        print(json.dumps({
            "success":        False,
            "error":          "nonce_request_failed",
            "raw_response":   nonce_resp,
            "strategy_notes": "TAP nonce request failed. Verify agent_id and app_id are correct.",
        }))
        sys.exit(0)

    sig       = base64.b64encode(priv.sign(nonce.encode())).decode()
    aud_param = f"&audience={args.audience}" if args.audience else ""

    c = http.client.HTTPSConnection(HOST, context=ctx)
    c.request(
        "POST", f"/v1/agents/auth/verify?app_id={args.app_id}{aud_param}",
        json.dumps({"challenge_id": challenge_id, "agent_id": agent_id, "signature": sig}).encode(),
        {"Content-Type": "application/json"},
    )
    token_resp    = json.loads(c.getresponse().read().decode())
    access_token  = token_resp.get("access_token")
    c.close()

    if access_token:
        emit_success(access_token, token_resp.get("refresh_token"), token_resp.get("expires_in", 3600), "tap")
    else:
        print(json.dumps({
            "success":        False,
            "error":          token_resp.get("error", "tap_verify_failed"),
            "raw_response":   token_resp,
            "strategy_notes": "TAP verify failed. The keypair may not match the registered public key.",
        }))

except Exception as e:
    print(json.dumps({
        "success":        False,
        "error":          type(e).__name__,
        "strategy_notes": f"Unhandled exception in botcha_token.py: {e}",
    }))
