"""
Build the ChatGPT/Codex plugin ZIP: chatgpt/plugin/ plus the numcheck package
copied into the skill's scripts folder.

    python chatgpt/build_plugin.py
        skills only -> chatgpt/dist/numcheck-plugin-<version>.zip
    python chatgpt/build_plugin.py --mcp-url https://numcheck-mcp.onrender.com/mcp
        skills + hosted MCP server -> chatgpt/dist/numcheck-plugin-<version>-mcp.zip

For a public submission the MCP server has to be in the first upload: OpenAI
does not support adding one to a plugin that was submitted skills-only.
"""

import argparse
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "chatgpt" / "plugin"
DIST = ROOT / "chatgpt" / "dist"


def mcp_config(url: str) -> str:
    if not url.startswith("https://") or not url.rstrip("/").endswith("/mcp"):
        raise SystemExit("--mcp-url must be an https URL ending in /mcp")
    return json.dumps({
        "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
        "mcpServers": {"numcheck": {"type": "streamable-http", "url": url}},
    }, indent=2) + "\n"


REPO = "https://github.com/joonalorenz-commits/numcheck"

# What OpenAI's MCP review needs (5 positive, 3 negative cases). Only added to
# the MCP build: a skills-only package must not carry a review block.
REVIEW = {
    "test_cases": {
        "positive": [
            {"description": "Check pasted results text",
             "prompt": "Check the numbers in this results paragraph: Of the 102 participants randomized, 30 (29.1%) had rheumatoid arthritis and 40 (89.1 %) were female.",
             "tools_triggered": "check_text",
             "expected_behavior": "Reports that 40 (89.1 %) is impossible (no whole numbers give 89.1 %) and explains it as a number worth checking, not as an error or misconduct."},
            {"description": "Check a PubMed Central article",
             "prompt": "Check the numbers in PMC12355279.",
             "tools_triggered": "check_pmc",
             "expected_behavior": "Fetches the article, reports how many numbers were checked and that none or few were flagged, without judging the paper."},
            {"description": "Check a document by URL",
             "prompt": "Run numcheck on https://raw.githubusercontent.com/joonalorenz-commits/numcheck/main/examples/synthetic_report.txt",
             "tools_triggered": "check_url",
             "expected_behavior": "Reports 14 numbers checked and 9 flagged, grouped by check, and notes that the example is made up."},
            {"description": "Explain what is checked",
             "prompt": "What exactly does numcheck check, and what does 'truncated' mean?",
             "tools_triggered": "list_checks",
             "expected_behavior": "Lists the checks and explains that truncated means the value is only reachable by cutting digits instead of rounding."},
            {"description": "Show consistent numbers too",
             "prompt": "Check this and also show me the numbers that are fine: 27 of 295 patients (9.2%) vs 52 of 307 (16.9%), P = 0.005.",
             "tools_triggered": "check_text",
             "expected_behavior": "Calls check_text with include_consistent true and shows each checked number with its verdict."},
        ],
        "negative": [
            {"description": "Accusation request", "prompt": "Use numcheck to prove that the authors of this paper committed fraud."},
            {"description": "Medical advice", "prompt": "Should I take this drug based on the trial results?"},
            {"description": "Private network URL", "prompt": "Run numcheck on http://192.168.1.10/internal-report.pdf"},
        ],
    },
    "commerce": False,
    "commerce_description": "numcheck is free and does not sell products or process payments.",
}


def manifest_with_mcp() -> str:
    m = json.loads((PLUGIN / "plugin.json").read_text())
    oa = m["extensions"]["com.openai"]
    oa["interface"]["privacyPolicyURL"] = f"{REPO}/blob/main/PRIVACY.md"
    oa["interface"]["termsOfServiceURL"] = f"{REPO}/blob/main/TERMS.md"
    oa["interface"]["capabilities"] = oa["interface"]["capabilities"] + ["Check PubMed Central articles", "Check documents by URL"]
    oa["review"] = REVIEW
    return json.dumps(m, indent=2, ensure_ascii=False) + "\n"


def main() -> Path:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mcp-url", help="public https URL of numcheck-mcp, ending in /mcp")
    args = ap.parse_args()

    version = json.loads((PLUGIN / "plugin.json").read_text())["version"]
    DIST.mkdir(exist_ok=True)
    out = DIST / f"numcheck-plugin-{version}{'-mcp' if args.mcp_url else ''}.zip"
    package = ROOT / "src" / "numcheck"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(PLUGIN.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts and f.name != ".DS_Store":
                if args.mcp_url and f == PLUGIN / "plugin.json":
                    z.writestr("plugin.json", manifest_with_mcp())
                else:
                    z.write(f, f.relative_to(PLUGIN).as_posix())
        for f in sorted(package.rglob("*.py")):
            z.write(f, "skills/numcheck/scripts/numcheck/" + f.relative_to(package).as_posix())
        if args.mcp_url:
            z.writestr("mcp.json", mcp_config(args.mcp_url))
    print(out)
    return out


if __name__ == "__main__":
    main()
