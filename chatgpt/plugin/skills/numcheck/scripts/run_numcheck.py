"""
Run numcheck on one document and print the result as JSON.

    python scripts/run_numcheck.py REPORT.pdf            flagged numbers only
    python scripts/run_numcheck.py REPORT.xml --all      also the consistent ones
    python scripts/run_numcheck.py --text - < paste.txt  text from stdin

The numcheck package sits next to this script, so nothing needs installing.
PDF input needs pypdf, which the ChatGPT sandbox has.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from numcheck import CHECKS, VERDICTS, check, document, summary  # noqa: E402
from numcheck.mcp_server import split_pages  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", help="PDF, JATS/PMC XML or text file")
    ap.add_argument("--text", help="'-' to read pasted text from stdin")
    ap.add_argument("--all", action="store_true", help="include consistent numbers")
    args = ap.parse_args()

    if args.text == "-":
        pages, source = split_pages(sys.stdin.read()), "pasted text"
    elif args.file:
        pages, source = document.read(args.file), Path(args.file).name
    else:
        ap.error("give a file or --text -")

    findings = check(pages)
    shown = findings if args.all else [f for f in findings if f.flagged]
    out = {
        "source": source,
        "pages": len(pages),
        "characters": sum(len(t) for t in pages.values()),
        "numbers_checked": len(findings),
        "flagged": sum(f.flagged for f in findings),
        "summary": summary(findings),
        "findings": [
            {k: v for k, v in f.as_dict().items() if k not in ("start", "end")}
            | {"meaning": VERDICTS.get(f.verdict, ""), "check_does": CHECKS.get(f.check, "")}
            for f in sorted(shown, key=lambda f: (f.page, f.start))
        ],
    }
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
