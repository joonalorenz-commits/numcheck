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

from numcheck import CHECKS, FLAGGED, VERDICTS, __version__, check, document, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="numcheck",
        description="Find numbers in clinical trial reports that cannot be right, without the data.",
        epilog="Checks: " + "; ".join(f"{k} ({v})" for k, v in CHECKS.items()))
    parser.add_argument("files", nargs="+", type=Path, help="PDF, JATS/PMC XML or text files")
    parser.add_argument("--all", action="store_true", help="also list numbers that are consistent")
    parser.add_argument("--json", action="store_true", help="write JSON to stdout")
    parser.add_argument("--csv", type=Path, metavar="FILE", help="write all findings to a CSV file")
    parser.add_argument("--version", action="version", version=f"numcheck {__version__}")
    args = parser.parse_args(argv)

    results = {}
    for path in args.files:
        findings = check(document.read(path))
        results[str(path)] = findings if args.all else [f for f in findings if f.flagged]
        if not args.json and not args.csv:
            _print(path, findings, results[str(path)])

    if args.json:
        json.dump({p: [f.as_dict() for f in fs] for p, fs in results.items()}, sys.stdout, ensure_ascii=False, indent=1)
        print()
    if args.csv:
        with args.csv.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["file", "page", "check", "verdict", "printed", "computed", "note", "quote", "start", "end"])
            for p, fs in results.items():
                for f in fs:
                    w.writerow([p, f.page, f.check, f.verdict, f.printed, f.computed, f.note, f.quote, f.start, f.end])
        print(f"{sum(map(len, results.values()))} findings written to {args.csv}")
    return 1 if any(f.flagged for fs in results.values() for f in fs) else 0


def _print(path: Path, findings, shown) -> None:
    flagged = [f for f in findings if f.flagged]
    print(f"{path.name}: {len(findings)} numbers checked, {len(flagged)} flagged")
    for f in sorted(shown, key=lambda f: (f.page, f.start)):
        print(f"\n  page {f.page} · {f.check} · {f.verdict}: printed {f.printed}"
              + (f", computed {f.computed}" if f.computed not in ("", "-") else ""))
        if f.note:
            print(textwrap.fill(f.note, 100, initial_indent="    ", subsequent_indent="    "))
        print(textwrap.fill(f"\"…{f.quote[-180:]}\"", 100, initial_indent="    ", subsequent_indent="    "))
    if flagged:
        print("\n  " + "; ".join(f"{v}: {VERDICTS[v]}" for v in FLAGGED))
    counts = summary(findings)
    if counts:
        print("  per check: " + ", ".join(f"{c} {sum(v.values())}" for c, v in sorted(counts.items())))
    print()


if __name__ == "__main__":
    sys.exit(main())
