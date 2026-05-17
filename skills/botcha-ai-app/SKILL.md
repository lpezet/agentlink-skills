---
name: botcha-ai-app
description: |
  Sets up (or retrieves) a Botcha.ai application — the organizational boundary that
  binds a human operator to a set of AI agents, and owns the trust, rate limits,
  and credentials those agents operate under.

  If one or more apps are already saved in ~/.config/botcha-ai/config.yml, returns
  the existing app_id without creating anything new. When multiple apps exist and the
  caller did not specify one, the human is asked to choose (or the first is used if
  the human is inactive).

  If no app exists, guides the human through creating one: collects their email and
  a display name, calls the Botcha.ai API, waits for an email verification code, and
  saves the new app_id to config.

  Returns a JSON block with app_id and created (true when a new app was just made).
context: fork
allowed-tools: Bash(python3 *), Bash(curl *)
arguments: []
version: 1.0.0
author: lpezet@gmail.com
metadata:
  hermes:
    tags: [auth, botcha.ai, setup]
    category: auth
---

## Step 0: Check for existing apps

Read `~/.config/botcha-ai/config.yml` and list any saved apps:

```bash
python3 - <<'EOF'
import json, pathlib
try:
    import yaml
    cfg = pathlib.Path.home() / ".config" / "botcha-ai" / "config.yml"
    if cfg.exists():
        data = yaml.safe_load(cfg.read_text()) or {}
        apps = data.get("apps", {})
        print(json.dumps({"success": True, "apps": list(apps.keys())}))
    else:
        print(json.dumps({"success": True, "apps": []}))
except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}))
EOF
```

- **One app found** → emit the output block (Step 3) with that `app_id` and `"created": false`. Stop.
- **Multiple apps found** → ask the human which one to use. Use the first one if the human is inactive or does not reply. Then go to Step 3.
- **No apps found** → proceed to Step 1.

## Step 1: Create app

Explain to the human that Botcha.ai requires an **app** to proceed. An app is the
organizational boundary that binds them (as the human operator) to their AI agents.
It owns the trust level, rate limits, and credentials that all agents operate under —
without one, agents cannot obtain a verified identity to authenticate to Botcha-protected
services.

Ask the human for:

- **Email address** (`<USER_EMAIL>`) — used to verify ownership and receive the verification code
- **App name** (`<APPNAME>`) — a short display name for this application. Provide "My Agent Fleet" as default.

Then create the app:

```bash
curl -s -X POST -H "Content-Type: application/json" \
  "https://botcha.ai/v1/apps" \
  -d '{"email": "<USER_EMAIL>", "name": "<APPNAME>"}' \
  > /tmp/botcha_ai_app.json
cat /tmp/botcha_ai_app.json
```

Tell the human to check their inbox for an email with a subject like
`"BOTCHA: Your verification code is 418930"` and to share the numeric code
(`<CODE>`) with you.

Once received, verify the email and activate the app:

```bash
python3 - <<'EOF'
import json, pathlib
data = json.loads(pathlib.Path("/tmp/botcha_ai_app.json").read_text())
print(json.dumps({"app_id": data.get("app_id"), "app_secret": data.get("app_secret")}))
EOF
```

Use the `app_id` and `app_secret` from that output to confirm verification:

```bash
curl -s -X POST -H "Content-Type: application/json" \
  "https://botcha.ai/v1/apps/<APP_ID>/verify-email" \
  -d '{"code": "<CODE>", "app_secret": "<APP_SECRET>"}'
```

Check the response: if it indicates success, tell the human they can now log into
their account at https://botcha.ai/login, then proceed to Step 2 yourself. If it indicates
failure (e.g. wrong code, expired), ask the human to recheck the code and retry the
verify call.

## Step 2: Save app to configuration

Merge the new app into `~/.config/botcha-ai/config.yml` without overwriting other
entries. Use the `created_at` timestamp from the API response if present; otherwise
use the current UTC time:

```bash
python3 - <<'EOF'
import json, pathlib, os, datetime
try:
    import yaml
    cfg_dir  = pathlib.Path.home() / ".config" / "botcha-ai"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = cfg_dir / "config.yml"
    data = (yaml.safe_load(cfg_file.read_text()) if cfg_file.exists() else None) or {}
    data.setdefault("apps", {})
    data["apps"]["<APP_ID>"] = {
        "created_at": "<CREATED_AT_OR_NOW>",
        "rate_limit":  100,
    }
    cfg_file.write_text(yaml.dump(data, default_flow_style=False))
    os.chmod(cfg_file, 0o600)
    print(json.dumps({"success": True}))
except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}))
EOF
```

Replace `<APP_ID>` with the actual app_id and `<CREATED_AT_OR_NOW>` with the
timestamp from the API or `datetime.datetime.utcnow().isoformat() + "Z"`.

## Step 3: Emit output

```json
{
  "success": true,
  "app_id": "...",
  "created": false
}
```

Set `"created": true` when a new app was made in Step 1–2, `false` when an existing
app was returned from Step 0.

On failure:

```json
{
  "success": false,
  "error": "<error message>",
  "strategy_notes": "<what failed and at which step>"
}
```
