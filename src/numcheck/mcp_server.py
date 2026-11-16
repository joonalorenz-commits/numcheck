"""
numcheck as an MCP server, so that ChatGPT, Claude and other assistants can
call it as a tool. Standard library only, like the rest of numcheck.

    numcheck-mcp                       stdio (Claude Desktop, Claude Code, Cursor)
    numcheck-mcp --http --port 8765    streamable HTTP at /mcp (ChatGPT apps, remote clients)

Tools (all read-only):
    check_text   text pasted by the user; pages separated by form feeds or "=== page N ==="
    check_pmc    a PubMed Central article by PMCID, fetched as JATS XML from NCBI
    check_url    a PDF, JATS XML or text file at a public URL
    list_checks  what numcheck recomputes and what the verdicts mean
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import socket
import sys
import tempfile
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from numcheck import CHECKS, FLAGGED, VERDICTS, __version__, check, document, summary

PROTOCOL = "2025-06-18"
MAX_BYTES = 25 * 1024 * 1024
MAX_TEXT = 2_000_000  # characters of pasted text
MAX_FINDINGS = 200
USER_AGENT = f"numcheck/{__version__} (+https://github.com/joonalorenz-commits/numcheck)"

INSTRUCTIONS = (
    "numcheck recomputes numbers in clinical trial reports from other numbers printed in the same "
    "document (percentages from counts, totals from groups, p values from test statistics, text from "
    "tables). A flagged number means 'cannot be reproduced from the other numbers on the page', not "
    "'the paper is wrong': there may be a reason the document does not show. Present flags as things "
    "to look at, quote the passage, and never call a paper or its authors fraudulent. Report what "
    "numcheck computed; do not invent corrected values or recompute numbers yourself."
)

_COMMON = {
    "include_consistent": {
        "type": "boolean",
        "description": "Also return numbers that matched. Default false: only flagged numbers.",
        "default": False,
    }
}

TOOLS = [
    {
        "name": "check_text",
        "title": "Check numbers in text",
        "description": (
            "Recompute percentages, table totals, p values and confidence intervals in text from a "
            "clinical trial report or paper (abstract, results, tables pasted as text). Separate pages "
            "with form feeds or lines like '=== page 2 ==='. Tables work best with one row per line."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "The report text."}, **_COMMON},
            "required": ["text"],
        },
    },
    {
        "name": "check_pmc",
        "title": "Check a PubMed Central article",
        "description": (
            "Fetch an open-access article from PubMed Central by PMCID (e.g. PMC7106986) and check its "
            "abstract, results section and tables."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"pmcid": {"type": "string", "description": "PMCID, with or without 'PMC'."}, **_COMMON},
            "required": ["pmcid"],
        },
    },
    {
        "name": "check_url",
        "title": "Check a document at a URL",
        "description": "Download a public PDF, JATS/PMC XML or plain-text file (max 25 MB) and check it.",
        "inputSchema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "http(s) URL of the document."}, **_COMMON},
            "required": ["url"],
        },
    },
    {
        "name": "list_checks",
        "title": "List numcheck checks",
        "description": "What numcheck recomputes and what each verdict means.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]
for _t in TOOLS:
    _t["annotations"] = {"title": _t["title"], "readOnlyHint": True, "destructiveHint": False,
                         "idempotentHint": True, "openWorldHint": _t["name"] != "list_checks"}


class ToolError(Exception):
    pass


# --- the tools ---------------------------------------------------------------

def split_pages(text: str) -> dict[int, str]:
    parts = re.split(r"\f|^\s*=+\s*page\s+\d+\s*=+\s*$", text, flags=re.I | re.M)
    parts = [p for p in parts if p.strip()] or [text]
    return {i: p for i, p in enumerate(parts, start=1)}


def report(pages: dict[int, str], source: str, include_consistent: bool = False) -> dict:
    findings = check(pages)
    flagged = [f for f in findings if f.flagged]
    shown = findings if include_consistent else flagged
    shown = sorted(shown, key=lambda f: (f.page, f.start))
    return {
        "source": source,
        "numbers_checked": len(findings),
        "flagged": len(flagged),
        "summary": summary(findings),
        "findings": [
            {k: v for k, v in f.as_dict().items() if k not in ("start", "end")}
            | {"verdict_meaning": VERDICTS.get(f.verdict, ""), "check_meaning": CHECKS.get(f.check, "")}
            for f in shown[:MAX_FINDINGS]
        ],
        "truncated": len(shown) > MAX_FINDINGS,
        "how_to_read": INSTRUCTIONS,
    }


def _check_public(url: str) -> None:
    """Refuse URLs that point into private networks (the server may run on a public host)."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise ToolError("Only http(s) URLs are supported.")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme.lower() == "https" else 80))
    except socket.gaierror as e:
        raise ToolError(f"Could not resolve {parts.hostname}.") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global or ip.is_multicast:
            raise ToolError("This URL points to a private or local address.")


class _PublicRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_public(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_PublicRedirects)


def _fetch(url: str) -> tuple[bytes, str]:
    _check_public(url)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with _OPENER.open(req, timeout=30) as r:
            data = r.read(MAX_BYTES + 1)
            ctype = r.headers.get("Content-Type", "")
    except ToolError:
        raise
    except Exception as e:  # network errors are reported to the model, not raised
        raise ToolError(f"Could not fetch {url}: {e}") from e
    if len(data) > MAX_BYTES:
        raise ToolError("Document is larger than 25 MB.")
    return data, ctype


def _pages_from_bytes(data: bytes, suffix: str) -> dict[int, str]:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / f"doc{suffix}"
        p.write_bytes(data)
        return document.read(p)


def check_pmc(pmcid: str, include_consistent: bool = False) -> dict:
    num = re.sub(r"(?i)^\s*pmc", "", pmcid.strip())
    if not num.isdigit():
        raise ToolError(f"'{pmcid}' is not a PMCID like PMC7106986.")
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={num}&rettype=xml"
    data, _ = _fetch(url)
    if b"<body" not in data and b"<abstract" not in data:
        raise ToolError(f"PMC{num} has no open-access full text that NCBI returns.")
    return report(_pages_from_bytes(data, ".xml"), f"PMC{num}", include_consistent)


def check_url(url: str, include_consistent: bool = False) -> dict:
    data, ctype = _fetch(url)
    if data[:5] == b"%PDF-" or "pdf" in ctype:
        suffix = ".pdf"
    elif data.lstrip()[:1] == b"<" and (b"<article" in data[:5000] or "xml" in ctype):
        suffix = ".xml"
    elif "html" in ctype:
        raise ToolError("This is a web page, not a document. Give the PDF link, a PMCID, or paste the text.")
    else:
        suffix = ".txt"
    return report(_pages_from_bytes(data, suffix), url, include_consistent)


def call_tool(name: str, args: dict) -> dict:
    inc = bool(args.get("include_consistent", False))
    if name == "check_text":
        text = args.get("text") or ""
        if not text.strip():
            raise ToolError("No text given.")
        if len(text) > MAX_TEXT:
            raise ToolError("Text is longer than 2 million characters; send the document as a URL instead.")
        return report(split_pages(text), "pasted text", inc)
    if name == "check_pmc":
        return check_pmc(str(args.get("pmcid", "")), inc)
    if name == "check_url":
        return check_url(str(args.get("url", "")), inc)
    if name == "list_checks":
        return {"checks": CHECKS, "verdicts": VERDICTS, "flagged_verdicts": list(FLAGGED), "how_to_read": INSTRUCTIONS}
    raise ToolError(f"Unknown tool {name}")


# --- JSON-RPC / MCP ----------------------------------------------------------

def handle(msg: dict) -> dict | None:
    """One JSON-RPC message in, one response out (None for notifications)."""
    mid, method = msg.get("id"), msg.get("method", "")
    if mid is None:
        return None

    def ok(result):
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    if method == "initialize":
        asked = (msg.get("params") or {}).get("protocolVersion") or PROTOCOL
        return ok({
            "protocolVersion": asked if asked <= PROTOCOL else PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "numcheck", "title": "numcheck", "version": __version__},
            "instructions": INSTRUCTIONS,
        })
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        p = msg.get("params") or {}
        try:
            result = call_tool(p.get("name", ""), p.get("arguments") or {})
        except ToolError as e:
            return ok({"content": [{"type": "text", "text": str(e)}], "isError": True})
        except Exception as e:  # a bug in a check must not kill the server
            return ok({"content": [{"type": "text", "text": f"numcheck failed: {type(e).__name__}: {e}"}], "isError": True})
        return ok({
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
            "structuredContent": result,
        })
    if method in ("resources/list", "prompts/list"):
        return ok({method.split("/")[0]: []})
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def serve_stdio() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            out = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            out = [r for r in map(handle, msg) if r] if isinstance(msg, list) else handle(msg)
        if out:
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            sys.stdout.flush()


class _Handler(BaseHTTPRequestHandler):
    server_version = f"numcheck-mcp/{__version__}"

    def _send(self, code: int, body: bytes = b"", ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/health"):
            self._send(200, b'{"ok":true,"server":"numcheck"}')
        elif self.path.split("?")[0] == "/.well-known/openai-apps-challenge":
            token = os.environ.get("OPENAI_APPS_CHALLENGE", "").strip()
            self._send(200, token.encode(), "text/plain") if token else self._send(404)
        else:
            self._send(405)  # no server-initiated stream

    def do_POST(self):
        if self.path.rstrip("/") != "/mcp":
            return self._send(404)
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_BYTES:
            return self._send(413)
        try:
            msg = json.loads(self.rfile.read(length) or b"null")
        except json.JSONDecodeError:
            return self._send(400, b'{"jsonrpc":"2.0","id":null,"error":{"code":-32700,"message":"Parse error"}}')
        out = [r for r in map(handle, msg) if r] if isinstance(msg, list) else handle(msg or {})
        if not out:
            return self._send(202)
        self._send(200, json.dumps(out, ensure_ascii=False).encode())

    def do_DELETE(self):
        self._send(200)

    def log_message(self, fmt, *args):
        sys.stderr.write("numcheck-mcp: " + fmt % args + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="numcheck-mcp", description="numcheck as an MCP server")
    ap.add_argument("--http", action="store_true", help="streamable HTTP at /mcp instead of stdio")
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8765)))
    args = ap.parse_args(argv)
    if args.http:
        srv = ThreadingHTTPServer((args.host, args.port), _Handler)
        sys.stderr.write(f"numcheck-mcp listening on http://{args.host}:{args.port}/mcp\n")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
    else:
        serve_stdio()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
