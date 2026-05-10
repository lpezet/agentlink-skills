#!/usr/bin/env python3
"""
List reputation events for the registered agent.
Usage: python3 botcha_reputation_events.py <app_id> [category] [limit]

Reads agent_id from ~/.config/botcha-ai/config.yml.

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

try:
    import yaml
except ImportError:
    print(json.dumps({"success": False, "error": "pyyaml not installed. Run: pip install pyyaml"}))
    sys.exit(1)

if len(sys.argv) < 2:
    print(json.dumps({"success": False, "error": "Usage: botcha_reputation_events.py <app_id> [category] [limit]"}))
    sys.exit(1)

APP_ID   = sys.argv[1]
CATEGORY = sys.argv[2] if len(sys.argv) > 2 else None
LIMIT    = sys.argv[3] if len(sys.argv) > 3 else None

CFG_FILE = pathlib.Path.home() / ".config" / "botcha-ai" / "config.yml"

try:
    cfg_data = yaml.safe_load(CFG_FILE.read_text())
    agent_id = cfg_data["apps"][APP_ID]["agent_id"]
except Exception as e:
    print(json.dumps({
        "success": False,
        "error": f"config_load_failed: {e}",
        "hint": "Run botcha_setup.py (botcha-ai skill) first.",
    }))
    sys.exit(1)

params = f"app_id={APP_ID}"
if CATEGORY:
    params += f"&category={CATEGORY}"
if LIMIT:
    params += f"&limit={LIMIT}"

ctx = ssl.create_default_context()
try:
    c = http.client.HTTPSConnection("api.botcha.ai", context=ctx)
    c.request("GET", f"/v1/reputation/{agent_id}/events?{params}")
    resp = json.loads(c.getresponse().read().decode())
    c.close()

    if resp.get("error"):
        print(json.dumps({"success": False, "error": resp["error"], "raw_response": resp}))
    else:
        events = resp.get("events") or resp.get("data") or []
        print(json.dumps({"success": True, "agent_id": agent_id, "events": events}))
except Exception as e:
    print(json.dumps({"success": False, "error": type(e).__name__, "detail": str(e)}))
