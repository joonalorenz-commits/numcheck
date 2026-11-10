"""
numcheck: find numbers in clinical trial reports that cannot be right, without the data.

    from numcheck import check, document
    findings = check(document.read("report.pdf"))
    for f in findings:
        if f.flagged:
            print(f.page, f.check, f.verdict, f.printed, f.note)

Every check recomputes a printed number from other numbers printed in the same
document: a percentage from its count and denominator, a column of categories
from its total, a p value from a test statistic, a number in the text from the
table it was copied from. Nothing is estimated, and no data are needed.
"""

from __future__ import annotations

from numcheck import checks, denominator, document, text_vs_table
from numcheck.finding import FLAGGED, VERDICTS, Finding

__version__ = "0.1.0"
__all__ = ["check", "summary", "Finding", "VERDICTS", "FLAGGED", "CHECKS", "document"]

CHECKS = {
    "fraction": "k of n (p%): percentage against count and denominator",
    "table_cell": "table cell k (p) against the N of its column",
    "category_sum": "categories adding up to 100 % cannot hold more people than N",
    "column_partition": "categories adding up to 100 % share one denominator",
    "row_total": "a Total column is the sum of the group columns",
    "grim_percent": "x.y% of patients is reachable with a group size of the document (GRIM)",
    "text_denominator": "k (p%) in the text against the denominator of the sentence, or any denominator (GRIM)",
    "text_vs_table": "k (p%) in the text against the same row in a table",
    "two_group_test": "p value of two proportions against Fisher's exact and chi-square tests",
    "test_statistic": "p value against t, F, chi-square or z statistic (like statcheck)",
    "ci_p": "estimate, 95% CI and p value against each other",
}


def check(pages: dict[int, str]) -> list[Finding]:
    """All checks over a document given as {page number: text}."""
    prepared = document.prepare(pages)
    flat = {n: document.normalize(t) for n, t in prepared.items()}
    all_headers = [x for t in flat.values() for x in checks.header_counts(t)]
    distinct = list(dict.fromkeys(all_headers))
    arms = (distinct[0], distinct[1]) if len(distinct) == 2 else None
    denominators = sorted(set(checks.total_counts(flat)) | set(all_headers) | ({sum(arms)} if arms else set()))
    out: list[Finding] = []
    header: list[int] = []
    for n, t in flat.items():
        new = checks.header_counts(t)
        header = new if len(new) >= 2 else header     # a table continues on the next page
        out += checks.fractions(n, t)
        out += checks.table_cells(n, t, header)
        out += checks.category_sums(n, t, header)
        out += checks.column_partitions(n, t)
        out += checks.row_totals(n, t, header)
        out += checks.grim_percents(n, t, denominators)
        out += checks.two_group_tests(n, t, arms)
        out += checks.test_statistics(n, t)
        out += checks.ci_p_values(n, t)
        if len(new) < 2:
            header = []                                # at most one continuation page
    out += text_vs_table.check(prepared)
    out += denominator.check(prepared)
    return out


def summary(findings: list[Finding]) -> dict[str, dict[str, int]]:
    """Counts per check and verdict."""
    out: dict[str, dict[str, int]] = {}
    for f in findings:
        out.setdefault(f.check, {}).setdefault(f.verdict, 0)
        out[f.check][f.verdict] += 1
    return out
