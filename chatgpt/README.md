# numcheck in ChatGPT

## 0. Plugin (skills, current format)

`plugin/` is an Agent Plugins package with one skill that runs numcheck's own
code. Build the ZIP with `python chatgpt/build_plugin.py` (copies `src/numcheck`
into the skill) and upload it under chatgpt.com/plugins → Add → Upload plugin
archive, or submit it at platform.openai.com/plugins.

Status 16.11.2026: the upload works and the listing shows correctly. In Codex and
in ChatGPT Work the skill folder is on disk and the script runs. In plain ChatGPT
chat (tested on a Free account) the model can read skill files but they are not
mounted in the Python sandbox, and the sandbox has no internet, so the script
cannot run there. For plain chat the plugin needs the MCP server below on a public
HTTPS host: see [HOSTING.md](HOSTING.md) and `build_plugin.py --mcp-url`.

Older ways:

## 1. Custom GPT (no server, 10 minutes)

ChatGPT runs numcheck itself in its Python sandbox (Code Interpreter). Nothing to host.

1. chatgpt.com → Explore GPTs → Create → Configure
2. **Name:** numcheck: trial report number checker
3. **Description:** Finds numbers in clinical trial reports that cannot be right, without the data. Percentages, table totals, p values, CIs, text vs tables. Open source.
4. **Instructions:** paste [instructions.md](instructions.md)
5. **Conversation starters:**
   - Check the numbers in this trial report (upload PDF or PMC XML)
   - Run the demo on the example report
   - Do the percentages in this results paragraph add up?
   - What exactly does numcheck check?
6. **Knowledge:** upload `numcheck.zip` and `example_report.txt` from this folder
7. **Capabilities:** Code Interpreter & Data Analysis ON, Web search off, image generation off
8. Test in the preview pane with the demo, then publish: "Anyone with the link" first, "GPT Store" once it behaves. The store needs a verified builder profile (name or domain).

Rebuild the zip after code changes: `cd src && zip -qr ../chatgpt/numcheck.zip numcheck -x '*/__pycache__/*'`

## 2. ChatGPT app / connector (MCP server)

`numcheck-mcp` is an MCP server (standard library only). Tools: `check_text`, `check_pmc`, `check_url`, `list_checks`, all read-only.

```bash
numcheck-mcp                       # stdio: Claude Desktop, Claude Code, Cursor
numcheck-mcp --http --port 8765    # streamable HTTP at http://127.0.0.1:8765/mcp
```

ChatGPT only talks to public HTTPS servers. To try it with your own account:
run `--http --host 0.0.0.0` on any small host (Render, Fly.io, a VPS) or tunnel
it locally, then in ChatGPT: Settings → Apps & Connectors → Advanced → Developer
mode → Create → URL `https://<host>/mcp`, no authentication. Listing it in the
public app directory goes through OpenAI's app submission review.

Claude Code: `claude mcp add numcheck -- numcheck-mcp`
