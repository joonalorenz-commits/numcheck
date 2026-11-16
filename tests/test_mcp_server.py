import json
from pathlib import Path

from numcheck import mcp_server as m

EXAMPLE = (Path(__file__).parent.parent / "examples" / "synthetic_report.txt").read_text()


def rpc(method, params=None, id=1):
    return m.handle({"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}})


def test_initialize_and_list():
    r = rpc("initialize", {"protocolVersion": "2025-03-26"})["result"]
    assert r["protocolVersion"] == "2025-03-26"
    assert "tools" in r["capabilities"]
    names = [t["name"] for t in rpc("tools/list")["result"]["tools"]]
    assert names == ["check_text", "check_pmc", "check_url", "list_checks"]
    assert all(t["annotations"]["readOnlyHint"] for t in rpc("tools/list")["result"]["tools"])


def test_notification_has_no_response():
    assert m.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_check_text_matches_cli_example():
    r = rpc("tools/call", {"name": "check_text", "arguments": {"text": EXAMPLE}})["result"]
    out = r["structuredContent"]
    assert out["flagged"] == 9 and out["numbers_checked"] == 14
    assert json.loads(r["content"][0]["text"])["flagged"] == 9
    assert all(f["verdict"] in m.FLAGGED for f in out["findings"])


def test_page_markers():
    assert len(m.split_pages("a\n=== page 2 ===\nb\n=== Page 3 ===\nc")) == 3


def test_errors_are_tool_results():
    r = rpc("tools/call", {"name": "check_pmc", "arguments": {"pmcid": "abc"}})["result"]
    assert r["isError"]
    r = rpc("tools/call", {"name": "check_url", "arguments": {"url": "file:///etc/passwd"}})["result"]
    assert r["isError"]
    assert "error" in rpc("nope")


def test_private_urls_are_refused():
    for url in ("http://127.0.0.1:8765/mcp", "http://localhost/", "http://169.254.169.254/latest/meta-data/",
                "http://10.0.0.1/x.pdf", "http://[::1]/"):
        r = rpc("tools/call", {"name": "check_url", "arguments": {"url": url}})["result"]
        assert r["isError"], url
        assert "private or local" in r["content"][0]["text"] or "resolve" in r["content"][0]["text"]


def test_text_limit():
    r = rpc("tools/call", {"name": "check_text", "arguments": {"text": "x" * (m.MAX_TEXT + 1)}})["result"]
    assert r["isError"]
