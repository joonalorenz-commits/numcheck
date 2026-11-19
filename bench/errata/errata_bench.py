"""
Benchmark on real, published errors: corrections (errata) of trial papers.

Injected errors (bench/injected_errors.py) measure whether a check fires when
we break a number on purpose. This benchmark asks the harder question: of the
numbers that journals later corrected, how many would numcheck have flagged
in the original article?

Steps (all public, open access only):
1. Europe PMC: errata in PMC that contain "should read" / "should have read"
   and mention a trial (query below), with the PMID of the corrected article.
2. From each erratum, the pairs "<wrong> should read <right>" whose numbers
   differ. The numbers that changed are the known errors.
3. The original article from PMC (JATS), run through numcheck.check.
4. For every changed number: was it checked at all (a finding with that
   printed value), and was it flagged (and with which confidence)?

    python bench/errata/errata_bench.py            # fetch + evaluate, writes bench/errata/out/
    python bench/errata/errata_bench.py --report   # only summarise existing results

Results are written per erratum to out/cases.jsonl, so a run can be resumed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / "src"))
from numcheck import __version__, check, document  # noqa: E402

OUT = ROOT / "out"
UA = f"numcheck-bench/{__version__} (+https://github.com/joonalorenz-commits/numcheck)"
QUERY = ('PUB_TYPE:"Published Erratum" AND OPEN_ACCESS:y AND ("should read" OR "should have read") '
         'AND (trial OR randomized)')
_NUM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")
_PAIR = re.compile(r"[\"“]([^\"“”]{3,600})[\"”][^\"“”]{0,140}?should (?:have )?(?:read|been|be)(?: as)?:?\s*[\"“]([^\"“”]{3,600})[\"”]",
                   re.I | re.S)


def get(url: str, tries: int = 4) -> bytes:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read(30_000_000)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 + 3 * i)
    return b""


def errata() -> list[dict]:
    out, cursor = [], "*"
    while True:
        url = ("https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&resultType=core&pageSize=500&"
               + urllib.parse.urlencode({"query": QUERY, "cursorMark": cursor}))
        d = json.loads(get(url))
        for r in d.get("resultList", {}).get("result", []):
            fors = [c["id"] for c in r.get("commentCorrectionList", {}).get("commentCorrection", [])
                    if c.get("type") == "Erratum for" and c.get("source") == "MED"]
            if r.get("pmcid") and fors:
                out.append({"erratum_pmcid": r["pmcid"], "erratum_title": r.get("title", ""), "original_pmid": fors[0]})
        nxt = d.get("nextCursorMark")
        if not nxt or nxt == cursor or not d.get("resultList", {}).get("result"):
            return out
        cursor = nxt


def jats(pmcid: str) -> bytes:
    """PMC XML, cached in out/xml so later versions are measured on the same files without fetching."""
    num = pmcid.upper().removeprefix("PMC")
    cache = OUT / "xml" / f"PMC{num}.xml"
    if cache.exists():
        return cache.read_bytes()
    time.sleep(0.4)
    data = get(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={num}&rettype=xml&tool=numcheck")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(data)
    return data


def pmcid_for(pmid: str) -> str | None:
    time.sleep(0.4)
    d = json.loads(get("https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?format=json&tool=numcheck&ids=" + pmid))
    for r in d.get("records", []):
        if r.get("pmcid"):
            return r["pmcid"]
    return None


def pairs(text: str) -> list[dict]:
    """'<wrong>' should read '<right>' with at least one changed number."""
    out = []
    for m in _PAIR.finditer(text):
        wrong, right = m.group(1), m.group(2)
        a, b = _NUM.findall(wrong), _NUM.findall(right)
        changed = [x for x in a if x not in b]
        if changed and len(a) == len(b):
            out.append({"wrong": wrong.strip(), "right": right.strip(), "changed": changed,
                        "changed_to": [y for y in b if y not in a]})
    return out


def evaluate(case: dict) -> dict:
    data = jats(case["erratum_pmcid"])
    text = " ".join(ET.fromstring(data).itertext()) if data else ""
    case["pairs"] = pairs(text)
    if not case["pairs"]:
        case["status"] = "no_numeric_pair"
        return case
    pmcid = pmcid_for(case["original_pmid"])
    if not pmcid:
        case["status"] = "original_not_in_pmc"
        return case
    case["original_pmcid"] = pmcid
    raw = jats(pmcid)
    if b"<body" not in raw:
        case["status"] = "original_no_fulltext"
        return case
    p = OUT / "tmp.xml"
    p.write_bytes(raw)
    findings = check(document.read(p))
    case["status"] = "evaluated"
    case["n_checked"] = len(findings)
    case["n_flagged"] = sum(f.flagged for f in findings)
    for pr in case["pairs"]:
        pr["results"] = []
        for num in pr["changed"]:
            hit = [f for f in findings if f.printed.lstrip("0") == num.lstrip("0") or f.printed == num]
            # A finding about the wrong number must also be near the wrong fragment's other numbers.
            ctx = set(_NUM.findall(pr["wrong"]))
            hit = [f for f in hit if len(ctx & set(_NUM.findall(f.quote))) >= min(2, len(ctx))] or hit[:0]
            pr["results"].append({
                "number": num,
                "checked": bool(hit),
                "flagged": any(f.flagged for f in hit),
                "confidence": max((f.confidence for f in hit if f.flagged), key=["", "low", "medium", "high"].index,
                                  default=""),
                "checks": sorted({f"{f.check}:{f.verdict}" for f in hit}),
            })
    return case


def report() -> dict:
    cases = [json.loads(l) for l in (OUT / "cases.jsonl").read_text().splitlines() if l.strip()]
    status = {}
    for c in cases:
        status[c["status"]] = status.get(c["status"], 0) + 1
    ev = [c for c in cases if c["status"] == "evaluated"]
    nums = [r for c in ev for p in c["pairs"] for r in p["results"]]
    checked = [r for r in nums if r["checked"]]
    flagged = [r for r in checked if r["flagged"]]
    by_conf = {}
    for r in flagged:
        by_conf[r["confidence"]] = by_conf.get(r["confidence"], 0) + 1
    papers_with_any_flag = sum(1 for c in ev if any(r["flagged"] for p in c["pairs"] for r in p["results"]))
    summary = {
        "errata_found": len(cases), "status": status,
        "evaluated_papers": len(ev),
        "corrected_numbers": len(nums),
        "corrected_numbers_checked": len(checked),
        "corrected_numbers_flagged": len(flagged),
        "flagged_by_confidence": by_conf,
        "recall_among_checked": round(len(flagged) / len(checked), 3) if checked else None,
        "recall_among_all_corrected": round(len(flagged) / len(nums), 3) if nums else None,
        "papers_with_a_corrected_number_flagged": papers_with_any_flag,
        "numcheck_version": __version__,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--reevaluate", action="store_true",
                    help="run the current numcheck again on all cases in cases.jsonl (uses out/xml cache)")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    if args.reevaluate:
        path = OUT / "cases.jsonl"
        old = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        new = []
        for c in old:
            base = {k: c[k] for k in ("erratum_pmcid", "erratum_title", "original_pmid")}
            try:
                new.append(evaluate(base))
            except Exception as e:
                base["status"] = f"error: {type(e).__name__}"
                new.append(base)
        path.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in new))
    elif not args.report:
        done = set()
        path = OUT / "cases.jsonl"
        if path.exists():
            done = {json.loads(l)["erratum_pmcid"] for l in path.read_text().splitlines() if l.strip()}
        todo = [c for c in errata() if c["erratum_pmcid"] not in done][: args.limit]
        print(f"{len(todo)} errata to evaluate", flush=True)
        with path.open("a") as fh:
            for i, c in enumerate(todo, 1):
                try:
                    c = evaluate(c)
                except Exception as e:  # keep going, record the failure
                    c["status"] = f"error: {type(e).__name__}"
                fh.write(json.dumps(c, ensure_ascii=False) + "\n")
                fh.flush()
                if i % 25 == 0:
                    print(f"{i}/{len(todo)}", flush=True)
    print(json.dumps(report(), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
