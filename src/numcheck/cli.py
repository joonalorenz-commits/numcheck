"""
Command line:

    numcheck report.pdf                 flagged numbers, readable
    numcheck article.xml --all          every checked number, also the consistent ones
    numcheck report.pdf --json          machine-readable
    numcheck *.xml --csv findings.csv   one CSV for many documents
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import textwrap
from pathlib import Path

from numcheck import CHECKS, CONFIDENCE, FLAGGED, VERDICTS, __version__, check, document, second_reader, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="numcheck",
        description="Find numbers in clinical trial reports that cannot be right, without the data.",
        epilog="Checks: " + "; ".join(f"{k} ({v})" for k, v in CHECKS.items()))
    parser.add_argument("files", nargs="+", type=Path, help="PDF, JATS/PMC XML or text files")
    parser.add_argument("--all", action="store_true", help="also list numbers that are consistent")
    parser.add_argument("--json", action="store_true", help="write JSON to stdout")
    parser.add_argument("--csv", type=Path, metavar="FILE", help="write all findings to a CSV file")
    parser.add_argument("--second-reader", action="store_true",
                        help="read every flagged PDF page again with pdfplumber; a flag the second reading "
                             "does not confirm gets a lower confidence (needs numcheck[pdf2])")
    parser.add_argument("--min-confidence", choices=("low", "medium", "high"), default="low",
                        help="only report flags at least this sure (default: all flags)")
    parser.add_argument("--version", action="version", version=f"numcheck {__version__}")
    args = parser.parse_args(argv)

    results = {}
    for path in args.files:
        findings = check(document.read(path))
        if args.second_reader:
            second_reader.confirm(path, findings)
        rank = {"low": 0, "medium": 1, "high": 2}
        keep = [f for f in findings if f.flagged and rank[f.confidence] >= rank[args.min_confidence]]
        results[str(path)] = findings if args.all else keep
        if not args.json and not args.csv:
            _print(path, findings, results[str(path)])

    if args.json:
        json.dump({p: [f.as_dict() for f in fs] for p, fs in results.items()}, sys.stdout, ensure_ascii=False, indent=1)
        print()
    if args.csv:
        with args.csv.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["file", "page", "check", "verdict", "confidence", "second_reader", "printed", "computed", "note",
                        "quote", "start", "end"])
            for p, fs in results.items():
                for f in fs:
                    w.writerow([p, f.page, f.check, f.verdict, f.confidence, f.second_reader, f.printed, f.computed,
                                f.note, f.quote,
                                f.start, f.end])
        print(f"{sum(map(len, results.values()))} findings written to {args.csv}")
    return 1 if any(f.flagged for fs in results.values() for f in fs) else 0


def _print(path: Path, findings, shown) -> None:
    flagged = [f for f in findings if f.flagged]
    print(f"{path.name}: {len(findings)} numbers checked, {len(flagged)} flagged")
    for f in sorted(shown, key=lambda f: (f.page, f.start)):
        sure = f" ({f.confidence} confidence)" if f.confidence else ""
        if f.second_reader:
            sure += f", second reader {f.second_reader}"
        print(f"\n  page {f.page} · {f.check} · {f.verdict}{sure}: printed {f.printed}"
              + (f", computed {f.computed}" if f.computed not in ("", "-") else ""))
        if f.note:
            print(textwrap.fill(f.note, 100, initial_indent="    ", subsequent_indent="    "))
        print(textwrap.fill(f"\"…{f.quote[-180:]}\"", 100, initial_indent="    ", subsequent_indent="    "))
    if flagged:
        print("\n  " + "; ".join(f"{v}: {VERDICTS[v]}" for v in FLAGGED))
        print("  confidence: " + "; ".join(f"{k}: {v}" for k, v in CONFIDENCE.items()))
    counts = summary(findings)
    if counts:
        print("  per check: " + ", ".join(f"{c} {sum(v.values())}" for c, v in sorted(counts.items())))
    print()


if __name__ == "__main__":
    sys.exit(main())
