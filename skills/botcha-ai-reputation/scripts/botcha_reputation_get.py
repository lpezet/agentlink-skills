#!/usr/bin/env python3
"""
Fetch the current reputation score and tier for the registered agent.
Usage: python3 botcha_reputation_get.py <app_id>

Reads agent_id from ~/.config/botcha-ai/config.yml.

Output JSON fields:
  success    bool
  agent_id   str
  score      int   (0-1000)
  tier       str
  events     int   total event count
  error      str   (on failure)
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
    print(json.dumps({"success": False, "error": "Usage: botcha_reputation_get.py <app_id>"}))
    sys.exit(1)

APP_ID   = sys.argv[1]
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

ctx = ssl.create_default_context()
try:
    c = http.client.HTTPSConnection("api.botcha.ai", context=ctx)
    c.request("GET", f"/v1/reputation/{agent_id}?app_id={APP_ID}")
    resp = json.loads(c.getresponse().read().decode())
    c.close()

    if resp.get("error"):
        print(json.dumps({"success": False, "error": resp["error"], "raw_response": resp}))
    else:
        print(json.dumps({
            "success":  True,
            "agent_id": agent_id,
            "score":    resp.get("score"),
            "tier":     resp.get("tier"),
            "events":   resp.get("event_count") or resp.get("events"),
        }))
except Exception as e:
    print(json.dumps({"success": False, "error": type(e).__name__, "detail": str(e)}))
