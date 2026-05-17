---
name: botcha-ai
description: |
  Botcha.ai is a reverse CAPTCHA that doubles as an identity and trust layer for AI agents.
  In order to interact with Botcha.ai, an application identifier must be either provided
  or created.
  An app is the organizational boundary that binds a human operator to a set of agents, 
  and owns the trust, rate limits, and credentials that agents operate under.
  Newly created and existing applications are tracked in a configuration file
  under ~/.config/botcha-ai/:
    config.yml — (chmod 600) keyed by app_id


  Call with:
    app_id:   <Botcha.ai app ID>       [required]
    audience: <resource server URL>    [optional — scopes the token]
    force:    "force"                  [optional — clears all cached tokens and forces
                                        a full re-authentication cycle, earning a fresh
                                        verification event for reputation]

  Returns a JSON block with access_token, refresh_token, agent_id (when newly
  registered for the app), auth_method, and strategy_notes (on failure).
allowed-tools: Bash(python3 *), Bash(curl *)
arguments: [app_id, audience, force]
version: 2.0.0
author: lpezet@gmail.com
metadata:
  hermes:
    tags: [auth, botcha.ai]
    category: auth
---

# Step 0: Check existing

Check if application already defined in configuration file:

```
TODO
```

If only one application defined, return it.
If more than one, ask which one to use, or use first one by default (or if human inactive).
If no configuration or no apps defined, proceed to step 1.

# Step 1: Create app

Ask human for email address (<USER_EMAIL>) to use to create an application in Botcha.ai to be able to register
as agent.
TODO: maybe need some more explanations to provide to human that this is necessary for this agent to
obtain a valid identity to use to authenticate to other services.
Use your existing name or define a new one (<AGENTNAME>).

```bash
curl -X POST -H "Content-Type: application/json" "https://botcha.ai/v1/apps" -d '{"email": "<USER_EMAIL>", "name": "<AGENTNAME>"}' > /tmp/botcha_ai_app.json
```

At this point, tell human to share verification code (<CODE>) received to their email address with a title like: "BOTCHA: Your verification code is 418930".
Now verify email to create application:

```bash
app_id=$(jq -r '.app_id' /tmp/botcha_ai_app.json)
app_secret=$(jq -r '.app_secret' /tmp/botcha_ai_app.json)
curl -X POST -H "Content-Type: application/json" "https://botcha.ai/v1/apps/${app_id}/verify-email" -d '{"code": "<CODE>", "app_secret": "'${app_secret}'"}'
```

You can tell human they can now log into their account at https://botcha.ai/login.

# Step 2: Save app to configuration

Save app_id (<APP_ID>) in configuration file (only the `apps.<APP_ID>` entry is necessary, the rest is optional):

```yml
apps:
  <APP_ID>:
    created_at: "2026-05-15T18:42:34.753Z"
    rate_limit: 100
```

You can now return the `app_id` to further skill or agents can use it.
