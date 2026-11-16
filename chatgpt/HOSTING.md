# Put numcheck online and into the ChatGPT plugin directory

Everything in the repo is ready. These steps need your own accounts, so you do
them; each takes a few minutes.

## 1. Host the MCP server on Render (free)

1. render.com → sign up with GitHub (account joonalorenz-commits).
2. Dashboard → **New** → **Blueprint** → choose the `numcheck` repository.
   Render reads `render.yaml` and creates the web service `numcheck-mcp`
   (Docker, free plan). Click **Apply**.
3. Wait for the first deploy (3–5 minutes). The URL is shown at the top, e.g.
   `https://numcheck-mcp.onrender.com`.
4. Check it: open `https://<your-url>/health` in the browser. It should show
   `{"ok":true,"server":"numcheck"}`.

The free plan sleeps after 15 minutes without requests. The first call after
that takes about a minute; ChatGPT may time out once and then work. For the
review and for real users, the cheapest paid plan (Starter) avoids this.

Every push to `main` deploys automatically.

Alternative: Fly.io with `fly.toml` (`fly launch --copy-config --no-deploy`,
then `fly deploy`). Fly needs a credit card even for the free allowance.

## 2. Try it in your own ChatGPT

chatgpt.com/plugins → **Add** → **Add custom MCP server** → URL
`https://<your-url>/mcp`, no authentication → confirm the warning →
**Create as a plugin**. Then in a new chat: "@numcheck check PMC12355279".

## 3. Build the plugin ZIP with the server

```bash
cd ~/code/numcheck
.venv/bin/python chatgpt/build_plugin.py --mcp-url https://<your-url>/mcp
```

This writes `chatgpt/dist/numcheck-plugin-0.1.0-mcp.zip` with the skill, the
server address, privacy policy and terms links, and the 5 + 3 review cases.

## 4. Submit to the public directory

1. platform.openai.com → Settings → Organization → General → **Verify** as an
   individual (ID check). This name is shown as the developer in the directory.
2. platform.openai.com/plugins → **Upload new or existing plugin** → choose
   the verified identity → upload the `-mcp.zip`. It must be a new plugin:
   OpenAI cannot add a server to a plugin that started skills-only.
3. Fix whatever the automated checks report, upload again if needed.
4. **MCPs** → connect `https://<your-url>/mcp`, no authentication, and wait for
   the tool scan.
5. Record a short demo video (1–2 minutes: the three example prompts in
   ChatGPT) and add its link as the demo recording.
6. **Submit for review**. After approval, **Publish plugin**.

The private skills-only test plugin on your account
(chatgpt.com/plugins, "numcheck") can be uninstalled once the hosted one works.
