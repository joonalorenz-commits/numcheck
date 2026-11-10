"""
Checks within one page: numbers that follow from other numbers on the same page.

- fraction        "27 of 295 (9.2%)": does the percentage match numerator and denominator?
- table_cell      "155 (52.5)  160 (52.1)" under "(N=295) (N=307)": the same for each column.
- category_sum    categories whose percentages add up to 100 cannot hold more people than N.
- column_partition categories adding up to 100 % share one denominator, the sum of their counts.
- row_total       a "Total" column must be the sum of the group columns in every row.
- grim_percent    "82.3% of patients": can any whole number of patients give this value?
                  (the GRIM test, Brown & Heathers 2017)
- two_group_test  "27 of 295 ... 52 of 307 ... (P = 0.005)": does Fisher's exact test or a
                  chi-square test give the printed p value?
- test_statistic  "t(48) = 2.10, P = 0.04": does the p value match the statistic? (like statcheck)
- ci_p            estimate, 95% CI and p value against each other.

A finding does not mean "wrong" but "cannot be reproduced from the other
numbers". Truncating instead of rounding is reported separately: some
programs truncate, and then the value is reachable, just not by rounding.
"""

from __future__ import annotations

import math
import re
from decimal import Decimal
from fractions import Fraction
from typing import Iterable, Optional

from numcheck.finding import Finding
from numcheck.stats import (chi_square, compare_percent, decimals, fisher_two_sided, p_chi_square, p_f,
                            p_t_two_sided, round_half_up)

NUMBER = r"\d+(?:\.\d+)?"
PERCENT = r"\s?%"


def _context(text: str, m: re.Match, before: int = 60, after: int = 30) -> str:
    return text[max(0, m.start() - before):m.end() + after].strip()


# ---------------------------------------------------------------- fraction
_INTEGER = r"\d{1,3}(?:,\d{3})+|\d+"
_FRACTION = re.compile(rf"(?<![\d.,])({_INTEGER})\s?(?:of|/)\s?({_INTEGER})(?: [a-z]+){{0,2}}\s?\(({NUMBER}){PERCENT}\)")


def fractions(page: int, t: str) -> list[Finding]:
    out = []
    for m in _FRACTION.finditer(t):
        k, n, p = int(m.group(1).replace(",", "")), int(m.group(2).replace(",", "")), m.group(3)
        verdict, computed = compare_percent(k, n, p)
        out.append(Finding(page, "fraction", _context(t, m), p, computed, verdict, f"{k}/{n}", *m.span(3)))
    return out


# -------------------------------------------------------------- table_cell
# "(N=295)", "(N = 1,030)", "N = 11 784" -- with thousands separators
_HEADER = re.compile(r"(?:\(\s?n|(?<![A-Za-z])N)\s?=\s?(\d{1,3}(?:[, ]\d{3})+|\d+)\b")
# count: a whole number, not the end of a decimal ("15.58 (3.50)") or of a number
# with thousands separator ("28,050"), no minus sign before it
_PAIR = rf"(?<![\d.,−-])(\d+)\s?\(\s?({NUMBER})\s?%?\s?\)"
# Another cell before or after (even an empty "0") means the row has more
# columns than the header, so matching cells to N would be a guess.
_PAIR_BEFORE = re.compile(rf"(?:\d\s?\(\s?{NUMBER}\s?%?\s?\)|(?<![\w.])0)\s*$")
_PAIR_AFTER = re.compile(r"^\s*(?:\d+\s?\(|0(?![\w.]))")


def _percent_row(before: str) -> bool:
    """Does the row belong to a table of percentages?

    Yes if the last bracket without a number in it announces a percentage
    ("n (%)", "no. (%)"). No if it clearly announces something else (SD, CI,
    events, "n < LLOQ"). Otherwise it depends on whether "(%)" appears shortly
    before: the label "n (%)" is often printed once per block.
    """
    brackets = [b for b in re.findall(r"\(([^()]*)\)", before[-300:])
                if not re.fullmatch(r"\s*[<>]?\s*[\d.,]+\s*%?\s*", b)]
    if brackets and "%" in brackets[-1] and "CV" not in brackets[-1]:
        return True
    if brackets and re.search(r"n\s?<|event|SD|StD|SE\b|range|CI|min|Q1|IQR|CV|mean|median|year|month|week|day|hour|"
                              r"\bcm\b|\bkg|\bmm|\bmg|\bml\b|score|/|\^", brackets[-1], re.I):
        return False
    return bool(re.search(r"\(\s?%\s?\)", before[-300:]))


def header_counts(t: str) -> list[int]:
    return [int(re.sub(r"[, ]", "", x)) for x in _HEADER.findall(t)]


def _any_denominator(p: str, denominators: Iterable[int], count: Optional[int] = None) -> Optional[tuple[str, int, int]]:
    """Is there a denominator (and count) that gives p when rounded? Otherwise at least truncated?"""
    truncated = None
    for n in denominators:
        for k in ([count] if count is not None else range(n + 1)):
            verdict, _ = compare_percent(k, n, p)
            if verdict == "consistent":
                return ("consistent", k, n)
            if verdict == "truncated" and truncated is None:
                truncated = ("truncated", k, n)
    return truncated


def table_cells(page: int, t: str, header: list[int]) -> list[Finding]:
    """Each cell "k (p)" against the N of its column.

    Many rows have their own, smaller denominator (subgroups, rows with
    their own n), and in tables split over several parts the match of N to
    columns is a guess. A finding is therefore only "impossible" when no
    denominator between k and the largest N on the page gives the percentage.
    """
    if len(header) < 2:
        return []
    upper = max(header)
    run = re.compile(r"\s+".join([_PAIR] * len(header)))
    out = []
    for m in run.finditer(t):
        if any(t[m.start(2 * i + 1) - 1:m.start(2 * i + 1)] == "/" for i in range(len(header))):
            continue  # "k/n (p)" is checked by fractions()
        # Only whole rows (as many cells as columns in the header) and only rows
        # of percentages: "%" in the cell or in the row label. "Mean (SD)" or
        # "n (events)" look the same.
        if _PAIR_BEFORE.search(t[:m.start()]) or _PAIR_AFTER.match(t[m.end():]):
            continue
        if "%" not in m.group(0) and not _percent_row(t[:m.start()]):
            continue
        for i, n in enumerate(header):
            k, p = int(m.group(2 * i + 1)), m.group(2 * i + 2)
            if k == 0 or float(p) > 100:
                continue
            verdict, computed = compare_percent(k, n, p)
            note = f"{k}/{n} (column {i + 1})"
            if verdict != "consistent":
                other = _any_denominator(p, range(k, upper + 1), k)
                if other and other[0] == "consistent":
                    verdict, note = "other_denominator", f"{k}/{other[2]} instead of /{n} (column {i + 1})"
                elif other:
                    verdict, note = "truncated", f"{k}/{other[2]} only when truncated (column {i + 1})"
                else:
                    verdict, note = "impossible", f"no denominator up to {upper} gives this with {k} (column {i + 1})"
            out.append(Finding(page, "table_cell", _context(t, m, 70, 0), p, computed, verdict, note, *m.span(2 * i + 2)))
    return out


# ------------------------------------------------------------ grim_percent
_PEOPLE = r"(?:patients|subjects|participants)"
_TOTALS = [re.compile(rf"total of (\d+) {_PEOPLE}"),
           re.compile(rf"(\d+) {_PEOPLE} were (?:randomi[sz]ed|enrolled)")]
_PERCENT_OF_PEOPLE = re.compile(rf"({NUMBER}){PERCENT} of (?:the |all )?{_PEOPLE}")
_CITATION = re.compile(r"\([A-Z][A-Za-z\-]+(?: et al\.?)?,? (?:19|20)\d{2}\s?\)")


def total_counts(pages: dict[int, str]) -> list[int]:
    return sorted({int(m.group(1)) for t in pages.values() for r in _TOTALS for m in r.finditer(t)})


def grim_percents(page: int, t: str, denominators: list[int]) -> list[Finding]:
    """"x.y% of patients": does any total or group size in the document give this value?

    Which group is meant is rarely stated in the same phrase, so every
    denominator found in the document counts; a finding only arises when
    none of them fits.
    """
    out = []
    for m in _PERCENT_OF_PEOPLE.finditer(t):
        p = m.group(1)
        if _CITATION.search(t[max(0, m.start() - 250):m.end() + 250]):
            continue  # a number from another study
        if "." not in p or not denominators:
            continue  # whole percentages are almost always reachable
        best = _any_denominator(p, denominators)
        listed = ", ".join(map(str, denominators))
        if best is None:
            out.append(Finding(page, "grim_percent", _context(t, m), p, "-", "impossible",
                               f"not reachable with any of the group sizes {listed}", *m.span(1)))
        elif best[0] == "truncated":
            out.append(Finding(page, "grim_percent", _context(t, m), p, f"{best[1]}/{best[2]}", "truncated",
                               f"with none of the group sizes {listed} when rounded, only when truncated", *m.span(1)))
        else:
            out.append(Finding(page, "grim_percent", _context(t, m), p, f"{best[1]}/{best[2]}", "consistent", "",
                               *m.span(1)))
    return out


# ---------------------------------------------------------- two_group_test
_P = re.compile(r"\bP\s?([=<>≤])\s?(0?\.\d+)", re.I)
_PAIRS_IN_SENTENCE = re.compile(r"\b(\d+) of (\d+)\b")
_TWO_GROUPS = re.compile(r"\b(\d+) in the [a-z\- ]+? group and (\d+) in the [a-z\- ]+? group")


def _p_matches(computed: float, sign: str, printed: str) -> bool:
    g = float(printed)
    if sign == "<":
        return computed < g
    if sign == ">":
        return computed > g
    return round_half_up(Fraction(computed), decimals(printed)) == Decimal(printed) or \
        abs(computed - g) <= 0.5 * 10 ** -decimals(printed) + 1e-12


def _tests(a: int, n1: int, b: int, n2: int) -> dict[str, float]:
    c, d = n1 - a, n2 - b
    n = n1 + n2
    stat, _, p_pearson = chi_square([[a, c], [b, d]])
    rows, cols = (a + c, b + d), (a + b, c + d)
    denom = rows[0] * rows[1] * cols[0] * cols[1]
    yates = n * max(0.0, abs(a * d - b * c) - n / 2) ** 2 / denom if denom else 0.0
    return {"Fisher exact": float(fisher_two_sided(a, c, b, d)),
            "Pearson chi-square": p_pearson,
            "chi-square with Yates correction": p_chi_square(yates, 1),
            "_statistic": stat}


_MODEL = re.compile(r"adjust|\bCI\b|confidence interval|odds|risk ratio|\b[ORH]R\b|difference|"
                    r"model|regression|\bz\s?=|one-sided|per-protocol", re.I)


def _two_groups(page: int, sentence: str, a: int, n1: int, b: int, n2: int, pm: re.Match) -> Finding:
    sign, printed = pm.group(1), pm.group(2)
    values = _tests(a, n1, b, n2)
    matching = [name for name, w in values.items() if not name.startswith("_") and _p_matches(w, sign, printed)]
    computed = ", ".join(f"{name} {w:.4f}" for name, w in values.items() if not name.startswith("_"))
    if matching:
        return Finding(page, "two_group_test", sentence, f"P {sign} {printed}", computed, "consistent",
                       "matches " + ", ".join(matching))
    if _MODEL.search(sentence):
        return Finding(page, "two_group_test", sentence, f"P {sign} {printed}", computed, "other_test",
                       "p value from a model or an estimate (adjusted, CI, risk difference)")
    note = "no common test for two proportions gives this p value"
    if sign == "=" and abs(values["_statistic"] - float(printed)) <= 0.5 * 10 ** -decimals(printed) + 1e-12:
        note += f"; the chi-square statistic is {values['_statistic']:.3f}, so the printed value is probably the statistic"
    return Finding(page, "two_group_test", sentence, f"P {sign} {printed}", computed, "inconsistent",
                   note + f" ({a}/{n1} vs {b}/{n2})")


def _sentences(t: str) -> Iterable[str]:
    return re.split(r"(?<=[.])\s+(?=[A-Z])", t)


def _with_position(f: Finding, t: str, sentence: str, pm: re.Match) -> Finding:
    base = t.find(sentence)
    if base >= 0:
        f.start, f.end = base + pm.start(2), base + pm.end(2)
    return f


def two_group_tests(page: int, t: str, arms: Optional[tuple[int, int]]) -> list[Finding]:
    out = []
    for sentence in _sentences(t):
        pm = _P.search(sentence)
        if not pm:
            continue
        hits = list(_PAIRS_IN_SENTENCE.finditer(sentence))
        if len(hits) == 2:
            pm = _P.search(sentence, hits[1].end())   # the p value belongs to the pairs before it
            if not pm:
                continue
            (a, n1), (b, n2) = [(int(x.group(1)), int(x.group(2))) for x in hits]
            if not (0 <= a <= n1 and 0 <= b <= n2 and 0 < a + b < n1 + n2):
                continue  # not a comparison of two proportions
            out.append(_with_position(_two_groups(page, sentence, a, n1, b, n2, pm), t, sentence, pm))
            continue
        tg = _TWO_GROUPS.search(sentence)
        if tg and arms and 0 < int(tg.group(1)) + int(tg.group(2)) < sum(arms):
            out.append(_with_position(_two_groups(page, sentence, int(tg.group(1)), arms[0], int(tg.group(2)),
                                                  arms[1], pm), t, sentence, pm))
    return out


# ---------------------------------------------------------- test_statistic
_STATISTICS = [
    ("t", re.compile(rf"\bt\s?\(\s?({NUMBER})\s?\)\s?=\s?(-?{NUMBER}),?\s?P\s?([=<>])\s?(0?\.\d+)", re.I)),
    ("F", re.compile(rf"\bF\s?\(\s?(\d+)\s?,\s?({NUMBER})\s?\)\s?=\s?({NUMBER}),?\s?P\s?([=<>])\s?(0?\.\d+)", re.I)),
    ("chi-square", re.compile(rf"(?:χ2|χ²|chi-square|chi2)\s?\(\s?(\d+)(?:,\s?N\s?=\s?\d+)?\s?\)\s?=\s?({NUMBER}),?"
                              rf"\s?P\s?([=<>])\s?(0?\.\d+)", re.I)),
    ("z", re.compile(rf"\bz\s?=\s?(-?{NUMBER}),?\s?P\s?([=<>])\s?(0?\.\d+)", re.I)),
]


def test_statistics(page: int, t: str) -> list[Finding]:
    """The printed statistic is itself rounded. The p value matches if it lies
    anywhere in the rounding range of the statistic (as in statcheck)."""
    out = []
    for kind, r in _STATISTICS:
        for m in r.finditer(t):
            g = m.groups()
            if kind == "t":
                df, raw, sign, printed = float(g[0]), g[1], g[2], g[3]
                p_of = lambda x, df=df: p_t_two_sided(abs(x), df)  # noqa: E731
            elif kind == "F":
                d1, d2, raw, sign, printed = int(g[0]), float(g[1]), g[2], g[3], g[4]
                p_of = lambda x, d1=d1, d2=d2: p_f(max(x, 0.0), d1, d2)  # noqa: E731
            elif kind == "chi-square":
                df, raw, sign, printed = int(g[0]), g[1], g[2], g[3]
                p_of = lambda x, df=df: p_chi_square(max(x, 0.0), df)  # noqa: E731
            else:
                raw, sign, printed = g[0], g[1], g[2]
                p_of = lambda x: math.erfc(abs(x) / math.sqrt(2))  # noqa: E731
            value, half = abs(float(raw)), 0.5 * 10 ** -decimals(raw)
            p_mid, p_edges = p_of(value), sorted((p_of(value - half), p_of(value + half)))
            ok = any(_p_matches(x, sign, printed) for x in (p_mid, *p_edges)) or (
                sign == "=" and p_edges[0] <= float(printed) <= p_edges[1])
            out.append(Finding(page, "test_statistic", _context(t, m, 20, 0), f"P {sign} {printed}", f"{p_mid:.4f}",
                               "consistent" if ok else "inconsistent", f"{kind} test, two-sided",
                               *m.span(m.lastindex)))
    return out


# ------------------------------------------------------------ category_sum
_CELL = re.compile(rf"(?<![\d.,−-])(\d+)\s?\(\s?({NUMBER})\s?%?\s?\)|(?<![\w.,(−-])0(?![\w.,)])")


def _rows(t: str, columns: int) -> list[list[tuple[int, str, tuple[int, int]]]]:
    """Table rows: runs of cells "k (p)" or "0" separated only by whitespace."""
    rows, current, end = [], [], -1
    for m in _CELL.finditer(t):
        cell = (int(m.group(1)), m.group(2), m.span(2)) if m.group(1) else (0, "0", m.span())
        if current and t[end:m.start()].strip():
            rows.append(current)
            current = []
        current.append(cell)
        end = m.end()
    if current:
        rows.append(current)
    return [r for r in rows if len(r) == columns and any(p != "0" for _, p, _ in r)]


def _complete(block: list, columns: int) -> bool:
    """Does every cell give exactly its percentage with its column sum as denominator?

    Only then are the rows a complete split. Sub-rows (reasons for stopping
    under "Discontinued") would otherwise count twice and no longer match the sum.
    """
    for s in range(columns):
        denom = sum(r[s][0] for r in block)
        if denom == 0:
            return False
        for k, p, _ in (r[s] for r in block):
            if p != "0" and compare_percent(k, denom, p)[0] == "inconsistent":
                return False
    return True


def category_sums(page: int, t: str, header: list[int]) -> list[Finding]:
    """Categories of a group: if their percentages add up to 100, their counts may not exceed N.

    Looks for consecutive rows whose percentages add up to 100 in every
    column (up to rounding per row) and where every cell gives exactly its
    percentage with the column sum as denominator. That is a complete split,
    and the sum of the counts is the number of people in that column. If it
    is larger than the N in the header, something is wrong. Smaller is
    allowed: missing values.
    """
    if len(header) < 2:
        return []
    # Total rows ("Any ...", 100 %) belong to no split; long blocks (nested lists
    # of classes and substances) reach 100 by chance more easily.
    rows = [r for r in _rows(t, len(header)) if all(float(p) < 100 for _, p, _ in r)]
    out, i = [], 0
    while i < len(rows):
        done, candidates = None, []
        for j in range(i + 1, min(len(rows), i + 8)):
            block = rows[i:j + 1]
            tolerance = [0.05 + sum(0.5 * 10 ** -decimals(r[s][1]) for r in block if r[s][1] != "0")
                         for s in range(len(header))]
            sums = [sum(float(r[s][1]) for r in block) for s in range(len(header))]
            if any(x > 100 + tol for x, tol in zip(sums, tolerance)):
                break
            if all(abs(x - 100) <= tol for x, tol in zip(sums, tolerance)) and _complete(block, len(header)):
                candidates.append(j)
        # Preferably the block whose sums are exactly the N in the header; otherwise the
        # shortest consistent one -- sub-rows after it do not belong to it.
        for j in candidates:
            if [sum(r[s][0] for r in rows[i:j + 1]) for s in range(len(header))] == header:
                done = j
                break
        else:
            done = candidates[0] if candidates else None
        if done is None:
            i += 1
            continue
        block = rows[i:done + 1]
        for s, n in enumerate(header):
            people = sum(r[s][0] for r in block)
            # If the sum appears as an N in the header, only the column is matched
            # differently; far above N, too. An error looks like this: just above N
            # and nowhere else.
            if people > n and people not in header and people - n <= max(3, n // 100):
                last = block[-1][s]
                out.append(Finding(page, "category_sum", t[max(0, last[2][0] - 160):last[2][1] + 5].strip(),
                                   f"N = {n}", str(people), "impossible",
                                   f"the categories of column {s + 1} add up to {people} people, "
                                   f"more than N = {n} in the table header", *last[2]))
        i = done + 1
    return out


# -------------------------------------------------------- column_partition
def _all_rows(t: str) -> list[list[tuple[int, str, tuple[int, int]]]]:
    """Like _rows, but any number of cells from two; the position covers the whole cell "k (p)".

    Rows are dropped when a cell is read uncertainly: a denominator in the
    cell ("256/262 (97.7%)", checked by fractions()), thousands separated by a
    space ("58 000 (39.1)"), or glued to its label ("<2599 (76.7%)", "0113 (87.6%)").
    """
    rows, current, end = [], [], -1
    for m in _CELL.finditer(t):
        before = t[max(0, m.start() - 3):m.start()]
        uncertain = m.group(1) and (before.endswith("/") or (re.search(r"\d\s$", before) and len(m.group(1)) == 3)
                                    or (before and not before[-1].isspace() and before[-1] not in "(")
                                    or (len(m.group(1)) > 1 and m.group(1).startswith("0")))
        if uncertain:
            current, end = [], m.end()
            rows.append([(-1, "0", m.span())])        # makes the row unusable
            continue
        cell = (int(m.group(1)), m.group(2), m.span()) if m.group(1) else (0, "0", m.span())
        if current and t[end:m.start()].strip():
            rows.append(current)
            current = []
        current.append(cell)
        end = m.end()
    if current:
        rows.append(current)
    return [r for r in rows if len(r) >= 2 and any(p != "0" for _, p, _ in r) and all(k >= 0 for k, _, _ in r)]


def _forced_to_100(block: list, s: int, denom: int, wrong: list) -> bool:
    """Forced to 100: correctly rounded the column would not add up to 100, printed it adds up to
    exactly 100, and every inconsistent cell is off by exactly one unit (largest remainder method)."""
    cells = [r[s] for r in block if r[s][1] != "0"]
    places = max(decimals(p) for _, p, _ in cells)
    unit = Decimal(1).scaleb(-places)
    printed = sum(Decimal(p) for _, p, _ in cells)
    correct = sum(round_half_up(Fraction(100 * k, denom), decimals(p)) for k, p, _ in cells)
    return (printed == 100 and correct != 100 and all(
        abs(Decimal(p) - round_half_up(Fraction(100 * k, denom), decimals(p))) == unit for k, p, _ in wrong))


def column_partitions(page: int, t: str) -> list[Finding]:
    """Categories whose percentages add up to 100 per column share one denominator: the sum of their counts.

    Consecutive rows with the same number of cells (2 to 7) whose percentages
    add up to exactly 100 in every column, up to rounding, are a split
    ("Female 19 (18) ..." / "Male 84 (82) ..."). Then every cell must match the
    denominator of its column, the sum of the counts, even without an N in the
    header. A finding is only reported when all other columns of the block
    match completely and the inconsistent cells lie in one column (at most
    two: a wrong count shifts the denominator and with it both cells). With
    only one column it takes at least three rows and at most one inconsistent
    cell.
    """
    rows = [r for r in _all_rows(t) if all(float(p) < 100 for _, p, _ in r)]
    out, i, reported = [], 0, set()
    while i < len(rows):
        columns = len(rows[i])
        hit = None
        for j in range(i + 1, min(len(rows), i + 7)):
            if len(rows[j]) != columns:
                break
            block = rows[i:j + 1]
            tolerance = [sum(0.5 * 10 ** -decimals(r[s][1]) for r in block if r[s][1] != "0") + 1e-9
                         for s in range(columns)]
            sums = [sum(float(r[s][1]) for r in block) for s in range(columns)]
            if any(x > 100 + tol for x, tol in zip(sums, tolerance)):
                break
            if not all(abs(x - 100) <= tol for x, tol in zip(sums, tolerance)):
                continue
            denoms = [sum(r[s][0] for r in block) for s in range(columns)]
            wrong = [(s, r[s]) for r in block for s in range(columns)
                     if r[s][1] != "0" and compare_percent(r[s][0], denoms[s], r[s][1])[0] != "consistent"]
            hit = (block, denoms, wrong)
            break
        if hit is None:
            i += 1
            continue
        block, denoms, wrong = hit
        wrong_columns = {s for s, _ in wrong}
        whole = all(r[s][1] == "0" or "." not in r[s][1] for r in block for s in range(columns))
        allowed = (len(wrong_columns) == 1 and len(wrong) <= 2
                   and (columns >= 2 or (len(block) >= 3 and len(wrong) == 1))
                   # Whole percentages leave a lot of room; the split must rest on other columns
                   and not (whole and columns < 3))
        if wrong and allowed:
            (s,) = wrong_columns
            forced = _forced_to_100(block, s, denoms[s], [c for _, c in wrong])
            for _, cell in wrong:
                if cell[2] in reported:
                    continue
                reported.add(cell[2])
                k, p, (a, b) = cell
                verdict, computed = compare_percent(k, denoms[s], p)
                f = Finding(page, "column_partition", t[max(0, a - 160):b + 5].strip(), p, computed, verdict,
                            f"{k}/{denoms[s]}: the {len(block)} categories of column {s + 1} add up to 100 %, "
                            f"their counts to {denoms[s]}", a, b)
                if forced:
                    f.verdict = "forced_to_100"
                    f.note += "; the percentages were forced to add up to exactly 100, correctly rounded they would not"
                out.append(f)
        i += len(block)
    return out


# --------------------------------------------------------------- row_total
def row_totals(page: int, t: str, header: list[int]) -> list[Finding]:
    """A "Total" column: if the header has an N that is the sum of the others, every row must add up too.

    "Hypnosis (n = 126) Sham (n = 124) Total (N = 250)": in every row with
    three cells, the count in the last is the sum of the two before. A row
    that does not add up is reported only when nearly all rows on the page
    add up; otherwise the column matching is a guess.
    """
    if len(header) < 3 or header[-1] != sum(header[:-1]):
        return []
    rows = [r for r in _all_rows(t) if len(r) == len(header)]
    adding_up = [r for r in rows if r[-1][0] == sum(k for k, _, _ in r[:-1])]
    if len(adding_up) < 3 or len(rows) - len(adding_up) > max(1, len(rows) // 5):
        return []
    out = []
    for r in rows:
        total = sum(k for k, _, _ in r[:-1])
        if r[-1][0] != total:
            k, p, (a, b) = r[-1]
            out.append(Finding(page, "row_total", t[max(0, r[0][2][0] - 120):b + 5].strip(), str(k), str(total),
                               "inconsistent", f"the groups add up to {total}, the Total column shows {k} "
                               f"({len(adding_up)} of {len(rows)} rows add up)", r[0][2][0], b))
    return out


# -------------------------------------------------------------------- ci_p
_MEASURE = (r"hazard ratio|odds ratio|risk ratio|relative risk|rate ratio|incidence rate ratio|"
            r"mean difference|risk difference|difference|(?-i:\b[aA]?HR\b|\b[aA]?OR\b|\bRR\b|\bIRR\b|\bMD\b|\bRD\b)")
_SIGNED = r"[−-]?\d+(?:\.\d+)?"
_INTERVAL = re.compile(
    rf"(?P<measure>{_MEASURE})(?:\s?\(\s?(?P<level_head>95)\s?%\s?CI(?:,\s?p-value)?\s?\)\s?[a-z]?)?[^();]{{0,150}}?"
    rf"(?P<est>(?:[−-]\s?)?\d+(?:\.\d+)?)\s?%?\s?[(\[]\s?"
    rf"(?:(?P<level>\d+(?:\.\d+)?)\s?%\s?(?:CI|confidence interval|CrI)?[,:]?\s?)?"
    rf"(?P<l>{_SIGNED})\s?%?\s?(?:to|–|—|,|-)\s?(?P<u>{_SIGNED})\s?%?\s?[)\];,]"
    rf"\s?(?:[)\]]\s?)?(?:[;,]\s?)?(?:[(\[]\s?)?\b(?:(?:two|2)-sided\s|nominal\s)?P(?:-value)?[a-z]?\s?[-:]?\s?"
    rf"(?P<sign>[=<>≤])?\s?(?P<p>0?\.\d+)", re.I)


def _number(text: str) -> float:
    return float(text.replace("−", "-").replace(" ", ""))


def _p_from_ci(est: float, lo: float, hi: float, ratio: bool) -> Optional[float]:
    """Approximation by Altman and Bland (BMJ 2011): p from estimate and 95% CI."""
    if ratio:
        if min(est, lo, hi) <= 0:
            return None
        est, lo, hi = math.log(est), math.log(lo), math.log(hi)
    se = (hi - lo) / (2 * 1.959964)
    if se <= 0:
        return None
    return math.erfc(abs(est / se) / math.sqrt(2))


def ci_p_values(page: int, t: str) -> list[Finding]:
    """Estimate, 95% CI and p value against each other.

    Certainly wrong: the estimate lies outside its interval; the interval
    excludes the null value but p >= 0.05, or the other way round. Roughly
    ("unclear"): the p value is far from the approximation from the interval.
    The approximation holds for Wald intervals; exact or adjusted methods
    often differ, hence only "unclear".
    """
    out = []
    for m in _INTERVAL.finditer(t):
        level = m.group("level") or m.group("level_head")
        if level and float(level) != 95:
            continue
        measure = m.group("measure").lower()
        ratio = bool(re.search(r"ratio|relative risk|^a?(?:hr|or)$|^i?rr$", measure.strip()))
        est, lo, hi = (_number(m.group(k)) for k in ("est", "l", "u"))
        if lo > hi:
            continue
        if re.match(r"[−-]\s", m.group("est")) and not (lo <= est <= hi) and lo <= -est <= hi:
            est = -est   # "a - 0.75": a dash, not a minus sign
        half = {k: 0.5 * 10 ** -decimals(m.group(k).replace("−", "").replace(" ", "")) for k in ("est", "l", "u")}
        sign, printed = m.group("sign") or "=", m.group("p")
        p_printed = float(printed)
        text = f"{m.group('measure')} {m.group('est')} ({m.group('l')} to {m.group('u')}), P {sign} {printed}"
        span = m.span("p")
        if est < lo - half["est"] - half["l"] or est > hi + half["est"] + half["u"]:
            out.append(Finding(page, "ci_p", _context(t, m, 20, 0), text, "-", "impossible",
                               "the estimate lies outside its confidence interval", *span))
            continue
        null = 1.0 if ratio else 0.0
        if abs(lo - null) <= half["l"] or abs(hi - null) <= half["u"] or (sign == "=" and p_printed == 0.05):
            continue  # borderline: rounding decides
        excludes = hi < null or lo > null
        significant = p_printed <= 0.05 if sign in "<≤" else (p_printed < 0.05 if sign == "=" else False)
        if sign == ">" and p_printed < 0.05:
            continue
        if level and excludes != significant:
            note = ("the 95% confidence interval excludes the null value, but the p value is not significant"
                    if excludes else "the p value is significant, but the 95% confidence interval contains the null value")
            out.append(Finding(page, "ci_p", _context(t, m, 20, 0), text, "-", "inconsistent", note, *span))
            continue
        corners = [_p_from_ci(e, a, b, ratio)
                   for e in (est - half["est"], est + half["est"])
                   for a in (lo - half["l"], lo + half["l"]) for b in (hi - half["u"], hi + half["u"])]
        corners = [x for x in corners if x is not None]
        if not corners:
            continue
        p_min, p_max = min(corners), max(corners)
        mid = _p_from_ci(est, lo, hi, ratio) or p_min
        if sign == "=":
            far = (p_printed > p_max * 3 or p_printed < p_min / 3) and not (p_printed < 0.001 and p_max < 0.001)
        elif sign in "<≤":
            far = p_min > p_printed * 3
        else:
            far = p_max < p_printed / 3
        out.append(Finding(page, "ci_p", _context(t, m, 20, 0), text, f"p ≈ {mid:.4f}",
                           "unclear" if far else "consistent",
                           "the p value is far from the approximation from the confidence interval "
                           "(Altman and Bland 2011); possible with exact or adjusted methods" if far else "", *span))
    return out
