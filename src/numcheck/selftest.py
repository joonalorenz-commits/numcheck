"""
Installation and operational check: fixed inputs with known, expected results.

    numcheck --selftest

Every case below is a short text with the verdict each check must give. If an
installation, a Python version or a code change alters any result, the self
test fails and names the case. Users who need documented evidence that the
tool works as intended (computerised system validation) run this after every
installation or update and keep the output together with the version.

The cases cover every check and every flagged verdict at least once. The
same cases are part of the test suite (tests/test_selftest.py).
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys

from numcheck import __version__, check

# (case id, requirement, text, expected list of (check, verdict, printed))
CASES = [
    ("FR-1", "a percentage that matches k/n is consistent",
     "In total, 30 of 102 (29.4%) patients responded.", [("fraction", "consistent", "29.4")]),
    ("FR-2", "a percentage that does not match k/n is flagged",
     "In total, 30 of 102 (29.1%) patients responded.", [("fraction", "inconsistent", "29.1")]),
    ("FR-3", "a truncated percentage is reported as truncated, not as wrong",
     "Excellent in 17/66 (25.7%) cases.", [("fraction", "truncated", "25.7")]),
    ("TC-1", "table cells are checked against the N of their column",
     "Drug (N=295) Placebo (N=307) Stent — no. (%) 246 (83.4) 250 (81.4)",
     [("table_cell", "consistent", "83.4"), ("table_cell", "consistent", "81.4")]),
    ("TC-2", "a table cell no denominator can produce is impossible",
     "Drug (N=295) Placebo (N=307) Stent — no. (%) 246 (38.4) 250 (81.4)",
     [("table_cell", "impossible", "38.4"), ("table_cell", "consistent", "81.4")]),
    ("TC-3", "a row with its own n is read against that n",
     "Survey (n=6) Bench (n=30) Clinical (n=36) Device n (%) Bentson 18 18 (100%) 16 (89%) 17 (94%)",
     [("table_cell", "consistent", "100"), ("table_cell", "consistent", "89"), ("table_cell", "consistent", "94")]),
    ("TS-1", "a p value that matches its t statistic is consistent, one that does not is flagged",
     "difference t(30) = 2.04, P = 0.05 and t(30) = 2.04, P = 0.01",
     [("test_statistic", "consistent", "P = 0.05"), ("test_statistic", "inconsistent", "P = 0.01")]),
    ("TG-1", "a two-group p value is compared with Fisher's exact test",
     "27 of 295 (9.2%) versus 52 of 307 (16.9%) (P = 0.005).", [("two_group_test", "consistent", "P = 0.005")]),
]


def _found(text: str) -> list[tuple[str, str, str]]:
    return [(f.check, f.verdict, f.printed) for f in check({1: text})]


def run() -> dict:
    results = []
    for cid, req, text, expected in CASES:
        got = _found(text)
        missing = [e for e in expected if e not in got]
        results.append({"case": cid, "requirement": req, "passed": not missing,
                        "expected": expected, "missing": missing})
    return {
        "numcheck_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cases": len(results),
        "passed": sum(r["passed"] for r in results),
        "fingerprint": hashlib.sha256(json.dumps(CASES).encode()).hexdigest()[:16],
        "results": results,
    }


def main() -> int:
    r = run()
    for x in r["results"]:
        print(f"{'PASS' if x['passed'] else 'FAIL'}  {x['case']:5}  {x['requirement']}")
        for m in x["missing"]:
            print(f"        expected {m}")
    print(f"\nnumcheck {r['numcheck_version']} · Python {r['python']} · {r['platform']}")
    print(f"{r['passed']}/{r['cases']} cases passed · case set {r['fingerprint']}")
    return 0 if r["passed"] == r["cases"] else 1


if __name__ == "__main__":
    sys.exit(main())
