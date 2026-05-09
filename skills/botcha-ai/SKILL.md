---
name: botcha-ai
description: |
  Obtains a Botcha.ai JWT access token for an AI agent. Manages the full
  identity lifecycle: first-run keypair generation, TAP agent registration per
  app, fast TAP challenge-response auth on subsequent runs, and challenge-solving
  fallback (speed/reasoning/hybrid/compute) when no registered identity exists.

  Config lives in two files under ~/.config/botcha-ai/ (both chmod 600):
    agent.yaml  — agent identity and Ed25519 keypair (shared across all apps)
    config.yaml — per-app registrations, keyed by app_id

  Call with:
    app_id:   <Botcha.ai app ID>       [required]
    audience: <resource server URL>    [optional — scopes the token]

  Returns a JSON block with access_token, refresh_token, agent_id (when newly
  registered for the app), auth_method, and strategy_notes (on failure).
metadata:
  version: 2.0.0
  author: lpezet@gmail.com
  hermes:
    tags: [auth, botcha.ai]
    category: auth
---

Your sole job: obtain a valid `access_token` and return it as a JSON block.
Follow these steps in order. Stop as soon as you have a token.

Config dir: `~/.config/botcha-ai/`  
Agent identity: `~/.config/botcha-ai/agent.yaml`  
App config: `~/.config/botcha-ai/config.yaml`

## CRITICAL RULES

1. **NEVER use curl for `/v1/token/verify`, `/v1/challenges/*/verify`, or any
   `/v1/agents/` POST.** Use Python for all of these. curl is allowed only for
   GET requests and `/v1/token/refresh`.
2. **Every** HTTP call to `api.botcha.ai` must include `?app_id=APP_ID_HERE`
   in the URL.
3. If you receive `APP_REGISTRATION_REQUIRED`, it means `app_id` was missing
   from that specific request — not that the app is unregistered. Retry with
   `?app_id=` present.
4. The `private_key_pem` in `agent.yaml` is sensitive. Never log or emit it.
5. `pyyaml` is required. If not installed, run `pip install pyyaml` before
   executing any step below.

---

## Step 0: Bootstrap agent identity

Load `agent.yaml`. If it is missing or incomplete, ask the user for any absent
values, generate the keypair, and write the file.

```bash
python3 - <<'EOF'
import pathlib
f = pathlib.Path.home() / ".config" / "botcha-ai" / "agent.yaml"
print(f.read_text() if f.exists() else "")
EOF
```

Parse the output. Required fields: `agent_name`, `operator`.  
Optional fields (with defaults if absent): `capabilities: [token:obtain]`,
`trust_level: verified`.  
Generated field (written by this step if absent): `public_key_pem`,
`private_key_pem`.

**If `agent_name` or `operator` is missing:** ask the user for each value.
When asking for `agent_name`, propose your own current agent name as the
default. When asking for `operator`, propose the user's name or organisation
if you know it from context.

**If `public_key_pem` / `private_key_pem` are missing:** generate the keypair
and write the full file:

```bash
python3 - <<'EOF'
import yaml, pathlib, os
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, PrivateFormat, NoEncryption
)

cfg_dir   = pathlib.Path.home() / ".config" / "botcha-ai"
cfg_dir.mkdir(parents=True, exist_ok=True)
agent_file = cfg_dir / "agent.yaml"

# Load existing data (may be partial)
data = yaml.safe_load(agent_file.read_text()) if agent_file.exists() else {}
if not data:
    data = {}

priv    = Ed25519PrivateKey.generate()
pub     = priv.public_key()
data["public_key_pem"]  = priv.public_key().public_bytes(
    Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
data["private_key_pem"] = priv.private_bytes(
    Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()

agent_file.write_text(yaml.dump(data, default_flow_style=False))
os.chmod(agent_file, 0o600)
print("Keypair generated and saved.")
EOF
```

After this step you have: `agent_name`, `operator`, `capabilities`,
`trust_level`, `public_key_pem`, `private_key_pem`.

---

## Step 0a: Bootstrap app config

Load the `app_id` section from `config.yaml`. If the section is absent, register
the agent with Botcha.ai for this app and write the section.

```bash
python3 - <<'EOF'
import yaml, pathlib

cfg_file = pathlib.Path.home() / ".config" / "botcha-ai" / "config.yaml"
data     = yaml.safe_load(cfg_file.read_text()) if cfg_file.exists() else {}
apps     = (data or {}).get("apps", {})
app_id   = "APP_ID_HERE"
print(yaml.dump(apps.get(app_id, {})))
EOF
```

**If the output contains a non-empty `agent_id`** → record `AGENT_ID`. Go to
the **Fast path** (if `refresh_token` present) or **Step 1** (TAP auth).

**If the output is empty** → register the agent for this app:

```bash
python3 - <<'EOF'
import yaml, json, pathlib, os, http.client, ssl

cfg_dir    = pathlib.Path.home() / ".config" / "botcha-ai"
agent_data = yaml.safe_load((cfg_dir / "agent.yaml").read_text())
cfg_file   = cfg_dir / "config.yaml"
cfg_data   = yaml.safe_load(cfg_file.read_text()) if cfg_file.exists() else {}
if not cfg_data:
    cfg_data = {}
cfg_data.setdefault("apps", {})

app_id = "APP_ID_HERE"

payload = json.dumps({
    "name":                agent_data["agent_name"],
    "operator":            agent_data["operator"],
    "version":             "1.0.0",
    "public_key":          agent_data["public_key_pem"],
    "signature_algorithm": "ed25519",
    "capabilities":        agent_data.get("capabilities", ["token:obtain"]),
    "trust_level":         agent_data.get("trust_level", "verified"),
    "app_id":              app_id,
}).encode()

ctx = ssl.create_default_context()
c   = http.client.HTTPSConnection("api.botcha.ai", context=ctx)
c.request("POST", f"/v1/agents/register/tap?app_id={app_id}", payload,
          {"Content-Type": "application/json"})
resp     = json.loads(c.getresponse().read().decode())
agent_id = resp.get("agent_id") or resp.get("id")
c.close()

if not agent_id:
    print(json.dumps({"success": False, "error": str(resp)}))
else:
    cfg_data["apps"][app_id] = {"agent_id": agent_id, "app_secret": "", "refresh_token": ""}
    cfg_file.write_text(yaml.dump(cfg_data, default_flow_style=False))
    os.chmod(cfg_file, 0o600)
    print(json.dumps({"success": True, "agent_id": agent_id}))
EOF
```

- `success: true` → record `AGENT_ID`. Go to **Step 1**.
- `success: false` → record error in `strategy_notes`. Fall through to **Step 2**.

**Note on `app_secret`:** After registering the *app* itself via `POST /v1/apps`,
Botcha.ai returns an `app_secret` shown only once. Paste it into the app's
section in `config.yaml` under `app_secret`. It is needed for keypair rotation
(`POST /v1/agents/:id/tap/rotate-key`) and not for normal operation.

---

## Fast path: refresh token

If the app section in `config.yaml` has a non-empty `refresh_token`:

```bash
curl -s -X POST "https://api.botcha.ai/v1/token/refresh?app_id=APP_ID_HERE" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "REFRESH_TOKEN_HERE"}'
```

Parse `access_token`. Emit the output block (Step 4). Stop.

---

## Step 1: TAP challenge-response auth

```bash
python3 - <<'EOF'
import yaml, json, http.client, ssl, base64, pathlib
from cryptography.hazmat.primitives.serialization import load_pem_private_key

cfg_dir    = pathlib.Path.home() / ".config" / "botcha-ai"
agent_data = yaml.safe_load((cfg_dir / "agent.yaml").read_text())
cfg_data   = yaml.safe_load((cfg_dir / "config.yaml").read_text())

app_id   = "APP_ID_HERE"
audience = "AUDIENCE_HERE"   # empty string if caller did not provide one
agent_id = cfg_data["apps"][app_id]["agent_id"]
priv     = load_pem_private_key(agent_data["private_key_pem"].encode(), password=None)

ctx = ssl.create_default_context()

# 1. Request nonce
c = http.client.HTTPSConnection("api.botcha.ai", context=ctx)
c.request("POST", f"/v1/agents/auth?app_id={app_id}",
          json.dumps({"agent_id": agent_id, "app_id": app_id}).encode(),
          {"Content-Type": "application/json"})
nonce_resp   = json.loads(c.getresponse().read().decode())
challenge_id = nonce_resp.get("challenge_id")
nonce        = nonce_resp.get("nonce")
c.close()

if not challenge_id or not nonce:
    print(json.dumps({"success": False, "error": str(nonce_resp)}))
    exit()

# 2. Sign nonce
sig = base64.b64encode(priv.sign(nonce.encode())).decode()

# 3. Verify → token
aud_param = f"&audience={audience}" if audience else ""
c = http.client.HTTPSConnection("api.botcha.ai", context=ctx)
c.request("POST", f"/v1/agents/auth/verify?app_id={app_id}{aud_param}",
          json.dumps({"challenge_id": challenge_id,
                      "agent_id": agent_id, "signature": sig}).encode(),
          {"Content-Type": "application/json"})
token_resp    = json.loads(c.getresponse().read().decode())
access_token  = token_resp.get("access_token")
refresh_token = token_resp.get("refresh_token")
c.close()

if access_token:
    # Persist refresh_token for next session
    cfg_data["apps"][app_id]["refresh_token"] = refresh_token
    cfg_file = cfg_dir / "config.yaml"
    cfg_file.write_text(yaml.dump(cfg_data, default_flow_style=False))
    print(json.dumps({"success": True, "access_token": access_token,
                      "refresh_token": refresh_token, "auth_method": "tap"}))
else:
    print(json.dumps({"success": False, "error": str(token_resp)}))
EOF
```

**If `success: true`** → go to **Step 4**. Done.  
**If `success: false`** → fall through to **Step 2**.

---

## Step 2: Challenge-solving fallback

Use this path only when there is no registered agent identity or TAP auth failed.

If the pre-built script is available:

```bash
python3 scripts/botcha_get_token.py APP_ID_HERE
```

Include `AUDIENCE_HERE` as a second argument if the caller provided one.

**If `success: true`** → go to **Step 4**.  
**If `needs_reasoning: true`** → go to **Step 3**.  
**If the script was not found** → use the manual flow below.

---

### Manual flow (when script is not available)

**2a. Fetch the challenge:**

```bash
curl -s "https://api.botcha.ai/v1/token?app_id=APP_ID_HERE"
```

Note `challenge.id` and `challenge.problems`.

**2b. Compute SHA-256 answers** (replace NUM1…NUM5 with actual problem numbers):

```bash
python3 -c "
import hashlib, json
nums = [NUM1, NUM2, NUM3, NUM4, NUM5]
print(json.dumps([hashlib.sha256(str(n).encode()).hexdigest()[:8] for n in nums]))
"
```

**2c. Verify — Python only, NOT curl:**

```bash
python3 -c "
import json, http.client, ssl
c = http.client.HTTPSConnection('api.botcha.ai', context=ssl.create_default_context())
payload = json.dumps({'id': 'CHALLENGE_ID_HERE', 'answers': ANSWERS_ARRAY_HERE}).encode()
c.request('POST', '/v1/token/verify?app_id=APP_ID_HERE', payload, {'Content-Type': 'application/json'})
print(c.getresponse().read().decode())
c.close()
"
```

---

## Step 3: Answer reasoning questions (only when needs_reasoning: true)

You have **30 seconds** from challenge issuance. Work quickly.

For each question read the `id` and build: `{"<question_id>": "<answer>", ...}`

**By category:**

- **Analogy** (`A is to B as C is to ?`): identify the A→B relationship, apply to C.
- **Math / word problem**: extract the numbers and compute directly.
- **Logic** (if/then, ordering, set membership): trace the conditions step by step.
- **Wordplay** (anagram, rhyme, letter pattern): work through it character by character.
- **Computer science** (complexity, data structures, algorithms): apply knowledge directly.
- **Pattern completion** (number or symbol sequences): find the rule, apply it.

If you see a category not listed, best-guess the answer and record the category
name in `strategy_notes` so the instructions can be extended.

Submit:

```bash
python3 scripts/botcha_verify_reasoning.py APP_ID_HERE CHALLENGE_ID TYPE '{"q-id-1":"answer1"}'
```

For hybrid challenges:

```json
{"speed_answers": [...], "reasoning_answers": {"q-id": "answer"}}
```

Go to Step 4.

---

## Step 4: Emit output

**Always emit this JSON block, even on failure.**

```json
{
  "success": true,
  "access_token": "...",
  "refresh_token": "...",
  "expires_in": 3600,
  "agent_id": "agent_... (only when newly registered this run, omit otherwise)",
  "auth_method": "tap | challenge | refresh",
  "challenge_type": "speed|reasoning|hybrid|compute (omit for tap/refresh)",
  "time_to_solve_ms": 175,
  "strategy_notes": "brief note — what worked, what was ambiguous"
}
```

On failure:

```json
{
  "success": false,
  "auth_method": "tap | challenge | refresh",
  "challenge_type": "...",
  "error": "...",
  "raw_challenge": "...",
  "raw_verify_response": "...",
  "strategy_notes": "be specific: what instruction was missing, what you tried"
}
```

The `strategy_notes` and `raw_*` fields on failure are the most valuable output —
they are the signal for improving these instructions.
