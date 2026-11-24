"""
A second, independent reading of the PDF for every flag.

Most false alarms in PDFs come from text extraction, not from arithmetic:
table columns that shift, a footnote marker read as a count, two rows read
as one. pypdf and pdfplumber extract text in different ways. A flag that
appears with both readings is more likely to be in the document itself; a
flag that disappears with the second reading is more likely an artefact of
the first one.

For each flagged finding from a page-local check, the page (and the page
before it, because a table header can sit there) is read again with
pdfplumber and checked again. The finding gets

    second_reader = "agrees"     the same check flags the same printed value
                    "disagrees"  the second reading does not flag it
                    ""           not compared (check needs the whole document,
                                 or pdfplumber is not installed)

A disagreement lowers the confidence by one level. It never removes a flag:
the reviewer decides.

Needs the optional dependency pdfplumber: pip install 'numcheck[pdf2]'.
"""

from __future__ import annotations

from pathlib import Path

from numcheck.finding import Finding

# Checks that only need the page itself (and a header on the page before).
PAGE_LOCAL = ("fraction", "table_cell", "row_total", "subgroup_mean", "category_sum", "column_partition",
              "ci_p", "test_statistic")


def available() -> bool:
    try:
        import pdfplumber  # noqa: F401
    except ImportError:
        return False
    return True


def _read_pages(path: Path, numbers: set[int]) -> dict[int, str]:
    import logging

    import pdfplumber

    logging.getLogger("pdfminer").setLevel(logging.ERROR)
    out = {}
    with pdfplumber.open(str(path)) as pdf:
        for n in sorted(numbers):
            if 1 <= n <= len(pdf.pages):
                out[n] = pdf.pages[n - 1].extract_text() or ""
    return out


def confirm(path: str | Path, findings: list[Finding]) -> list[Finding]:
    """Set second_reader on every flagged page-local finding. Returns the same list."""
    from numcheck import check

    path = Path(path)
    todo = [f for f in findings if f.flagged and f.check in PAGE_LOCAL]
    if not todo or path.suffix.lower() != ".pdf" or not available():
        return findings
    pages = {f.page for f in todo} | {f.page - 1 for f in todo if f.page > 1}
    texts = _read_pages(path, pages)
    cache: dict[int, set[tuple[str, str]]] = {}
    for f in todo:
        if f.page not in cache:
            window = {n: texts[n] for n in (f.page - 1, f.page) if n in texts}
            again = check(window)
            cache[f.page] = {(g.check, g.printed) for g in again if g.flagged and g.page == f.page}
        f.second_reader = "agrees" if (f.check, f.printed) in cache[f.page] else "disagrees"
    return findings
