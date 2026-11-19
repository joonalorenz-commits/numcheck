import json

from numcheck import cli, selftest


def test_selftest_passes():
    r = selftest.run()
    assert r["passed"] == r["cases"], [x for x in r["results"] if not x["passed"]]


def test_audit_log_is_reproducible(tmp_path):
    doc = tmp_path / "r.txt"
    doc.write_text("In total, 30 of 102 (29.1%) patients responded.")
    log = tmp_path / "audit.jsonl"
    cli.main([str(doc), "--audit-log", str(log), "--json"])
    cli.main([str(doc), "--audit-log", str(log), "--json"])
    a, b = [json.loads(l) for l in log.read_text().splitlines()]
    assert a["file_sha256"] == b["file_sha256"] and a["findings_sha256"] == b["findings_sha256"]
    assert a["flagged"] == 1 and a["flagged_high"] == 1
