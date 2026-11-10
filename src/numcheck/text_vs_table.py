"""
Text against table: does the body text give the same number as the table?

A report states the important results twice, in the tables and in the text
(synopsis, results section). The text is often written by hand, or not
updated after a new data cut. Without the analysis data one can still check
whether both say the same:

- Every statement "k (p%)", "k/n (p%)" or "k of n (p%)" in running text is
  looked up in all table rows of the document.
- If some cell has exactly this count and percentage, it matches.
- Otherwise a row is only matched when

  0. a comparison next to it ("58 (5.4%) vs 161 (15.0%)", "... in the
     lateral group and ...") appears exactly in one row and the group name in
     the text identifies the column header; then exactly that cell must match;
  1. a neighbouring comparison, or otherwise another statement of the same
     sentence, appears exactly in one row (and the sentence quotes only that row);
  2. all content words of the row label are in the clause of the statement; or
  3. the percentage occurs exactly once in all tables and one word of the
     row label is in the clause.

Reported is the same percentage with a different count, or the same count
with a different percentage (without a comparison in the sentence only from
20 people and under 2 points difference; otherwise it is more likely a
different denominator). Statements that cannot be matched to a row stay
unchecked and are not counted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from numcheck.checks import NUMBER
from numcheck.finding import Finding

# Whole numbers, also with thousands separators: 1,696 and 14 403
_WHOLE = r"\d{1,3}(?:[, ]\d{3})+(?![\d.])|\d+"
_CELL = re.compile(rf"(?<![\d.,−-])({_WHOLE})(?:\s?/\s?({_WHOLE}))?\s?\(\s?({NUMBER})\s?%?\s?\)")
# In text: "58 (5.4%)", "58/1073 (5.4%)", "58 of 1073 (5.4%)", "58 patients (5.4%)",
# also "962 patients (81.7% of the treated patients)"
_STATEMENT = re.compile(rf"(?<![\d.,−-])(?<!\d )({_WHOLE})(?:\s?(?:/|of|out of)\s?({_WHOLE}))?(?: [a-z]+){{0,2}}"
                        rf"\s?[(\[]\s?({NUMBER})\s?%(?: of [a-z ]{{3,40}})?\s?[)\]]")
# Tables with a separate percentage column: "N %" in the header, cells "324 82.7" without brackets
_N_PERCENT = re.compile(r"(?:^|\s|\()[Nn]\s+%(?:\s|$|\))")
_PAIRS = re.compile(r"(?<![\d.,])((?:\d+ (?:100\.0|\d{1,2}\.\d|0)(?: |$)){2,})\s*$")


def _int(x: str) -> int:
    return int(re.sub(r"[, ]", "", x))


_WORD = re.compile(r"[a-zäöüß]{4,}")
_FILLER = {"with", "from", "that", "this", "were", "was", "have", "had", "their", "than", "patients", "patient",
           "participants", "participant", "subjects", "subject", "group", "groups", "arm", "arms", "total",
           "number", "percentage", "events", "event", "least", "more", "during", "after", "before", "each",
           "overall", "treated", "treatment", "receiving", "received", "versus", "compared", "respectively",
           "any", "both", "other", "none", "yes", "missing", "unknown", "study", "period", "week", "weeks",
           "month", "months", "days", "year", "years", "visit", "baseline", "randomized", "randomised",
           "placebo", "control", "intervention", "lateral", "supine", "standard", "care", "usual", "dose"}


def _stem(w: str) -> str:
    return w[:6]


def _content(text: str) -> set[str]:
    """Content words, plus standalone whole numbers: "Grade 1" is not "Grade 3"."""
    words = {_stem(w) for w in _WORD.findall(text.lower()) if w not in _FILLER}
    if not words:
        return set()
    return words | set(re.findall(r"(?<![\d.,])\d{1,2}(?![\d.,%])", text))


@dataclass
class _Row:
    page: int
    label: str
    cells: list[tuple[int, str]]
    # counts that can also be read differently: "≤3 168 (1.4)" is 168, not 3168
    alternatives: tuple[int, ...] = ()
    # column names from the table header, one per cell, only when the count matches
    header: tuple[str, ...] = ()

    def sums(self) -> set[int]:
        """All sums of two or more cells: totals over several groups."""
        ks = [k for k, _ in self.cells][:10]
        return {sum(k for i, k in enumerate(ks) if mask >> i & 1)
                for mask in range(1, 1 << len(ks)) if bin(mask).count("1") >= 2}


_GROUP_N = re.compile(r"[(\[]\s?[nN]\s?=\s?\d[\d, ]*[)\]]|(?<![A-Za-z])N\s?=\s?\d[\d,]*")
_GENERIC = {"group", "groups", "arm", "arms", "the", "and", "with", "total", "all", "overall", "patients",
            "participants", "subjects", "no", "characteristic", "variable", "outcome", "outcomes", "events"}


def _name_words(text: str) -> set[str]:
    return {w[:6] for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in _GENERIC}


def _column_names(line: str) -> list[str]:
    """"Outcome Lateral group (n=1073) Supine group (n=1070)" -> ["Lateral group", "Supine group"].

    A column name stands before its "(n = ...)"; of the first name only the end
    belongs to it, before that is the heading of the first column.
    """
    names, start = [], 0
    for m in _GROUP_N.finditer(line):
        piece = line[start:m.start()].strip(" ,;")
        names.append(" ".join(piece.split()[-3:]) if not names else piece)
        start = m.end()
    return names


def _table_rows(page: int, t: str) -> list[_Row]:
    """Rows with at least two cells "k (p)"; the label is the text before them.

    Generic labels ("Yes", "Male", "Grade 3") get the last line without numbers
    before them as a heading.
    """
    out, heading, header = [], "", []
    separate_percent = bool(_N_PERCENT.search(t))
    for line in t.split("\n"):
        if separate_percent:
            m = _PAIRS.search(line)
            if m:
                numbers = m.group(1).split()
                cells = [(int(k), q) for k, q in zip(numbers[::2], numbers[1::2])]
                label = line[:m.start()].strip()
                # percentage fits the cell: 0 only with 0, otherwise > 0 and at most 100
                if all((k == 0) == (float(q) == 0) for k, q in cells) and not re.search(r"\d$", label):
                    if label and not _content(label):
                        label = f"{heading} {label}".strip()
                    out.append(_Row(page, label, cells))
                    continue
        if len(_GROUP_N.findall(line)) >= 2:
            header = _column_names(line)
            continue
        cells = list(_CELL.finditer(line))
        # A table row has no words between its cells; running text does
        between = [line[a.end():b.start()] for a, b in zip(cells, cells[1:])]
        if any(len(re.findall(r"[A-Za-z]{2,}", x)) > 1 for x in between):
            cells = []
        if len(cells) < 2:
            if line.strip() and not re.search(r"\d", line) and len(line) < 120:
                heading = line.strip()
            continue
        label = line[:cells[0].start()].strip()
        # No letters, or numbers glued together, before the first cell ("CVD 25 240150 265 (16.8)")
        if label and (not re.search(r"[A-Za-z]", label) or re.search(r"\d{4,}$", label)):
            continue
        if not _content(label):
            label = f"{heading} {label}".strip()
        alternatives = tuple(_int(m.group(1).split(" ", 1)[1]) for m in cells if " " in m.group(1))
        out.append(_Row(page, label, [(_int(m.group(1)), m.group(3)) for m in cells], alternatives,
                        tuple(header) if len(header) == len(cells) else ()))
    return out


def _running_text(t: str) -> bool:
    return len(re.findall(r"\b[a-z]{3,}\b", t)) >= 8


def _sentences(t: str):
    """Sentences with their position in the text; "." before a digit (5.4) does not split.

    A line break only splits after the end of a sentence or a colon, and after
    short lines (headings, table cells): in a PDF running text breaks mid-sentence.
    """
    start = 0
    for m in re.finditer(r"(?<=[a-z)%\]])\.\s+(?=[A-Z])|\n", t):
        if m.group() == "\n":
            line = t[t.rfind("\n", 0, m.start()) + 1:m.start()]
            if len(line) >= 60 and not line.rstrip().endswith((".", ":")):
                continue
        yield start, t[start:m.start() + 1]
        start = m.end()
    yield start, t[start:]


def _equal(a: str, b: str) -> bool:
    return abs(float(a) - float(b)) < 1e-9


def _partly(label: set[str], words: set[str]) -> bool:
    """At least half of the label is in the clause, and all numbers from it ("Grade 3")."""
    numbers = {w for w in label if w.isdigit()}
    return (bool(label) and numbers <= words
            and len(label & words) >= max(1, (len(label) + 1) // 2))


def _close(k: int, zk: int) -> bool:
    """A miscount is close to the correct value. 6 instead of 4 with the same percentage
    rather means: another population with another denominator."""
    return abs(k - zk) <= max(1, zk // 4)


def _equal_exact(a: str, b: str) -> bool:
    """The same percentage with as many decimals: 12.20 is a different estimate from 12.2."""
    places = [len(x.split(".")[1]) if "." in x else 0 for x in (a, b)]
    return _equal(a, b) and places[0] == places[1]


def _equal_rounded(a: str, b: str) -> bool:
    """The same value, only rounded differently (5.4 and 5.45, 10 and 10.2)?"""
    places = min(len(x.split(".")[1]) if "." in x else 0 for x in (a, b))
    return round(float(a), places) == round(float(b), places) or abs(float(a) - float(b)) <= 0.5 * 10 ** -places + 1e-9


def _table_like(sentence: str) -> bool:
    """Table remains in the text: several cells right after each other."""
    return len(re.findall(rf"\(\s?{NUMBER}\s?%?\s?\)\s?\d", sentence)) >= 2


def _clause(sentence: str, m: re.Match) -> str:
    """The clause of a statement.

    Backwards to the previous comma or semicolon, but not across a previous
    statement: in "115 of 597 (19.3%) at birth to 71 of 570 (12.5%) at 12 months"
    "at birth" belongs to the first number. Forwards to the next comma,
    semicolon or bracket.
    """
    before = sentence[:m.start()]
    statement = max(before.rfind("%)"), before.rfind("%]"))
    comma = max(before.rfind(","), before.rfind(";"))
    start = m.start() if statement > comma else (comma + 1 if comma >= 0 else max(0, m.start() - 150))
    after = sentence[m.end():]
    end = min([x for x in (after.find(","), after.find(";"), after.find("(")) if x >= 0] or [len(after)])
    return sentence[start:m.end() + min(end, 80)]


def _finding(n, quote, k, p, row, zk, zp, why, span) -> Finding:
    return Finding(n, "text_vs_table", quote, f"{k} ({p}%)", f"{zk} ({zp})", "inconsistent",
                   f"the table on page {row.page} shows {zk} ({zp}) in the row \"{row.label[:80]}\": {why}", *span)


def _column(row: _Row, text: str) -> Optional[int]:
    """Which column does a piece of text mean? Only unambiguously via the group names in the header."""
    words = _name_words(text)
    hits = [i for i, name in enumerate(row.header) if _name_words(name) & words]
    return hits[0] if len(hits) == 1 else None


_COMPARISON = re.compile(r"\b(?:vs|versus|v|compared (?:with|to)|than)\b\.?", re.I)


def _comparison(between: str) -> bool:
    """Are two statements a comparison ("58 (5.4%) vs 161 (15.0%)", "58 (5.4%) in the lateral
    group and 161 (15.0%) in the supine group") rather than a list of different things
    ("... were alive, 37 (12.5%) were lost ...")?"""
    if ";" in between:
        return False
    if _COMPARISON.search(between):
        return True
    # "103 (26.2%) in the placebo group, 90 (23.0%) in the 9 mg bid group, and 85 ...": between the
    # statements only a group name, separated by a comma or "and"
    group = re.fullmatch(r"\s*(?:patients?\s+|participants?\s+)?(?:in|on|with|for|under)\s+(?:the\s+)?[\w\s+\-–./]{1,40}?"
                         r"\b(?:group|arm|cohort)s?\)?\s*(?:,\s*)?(?:and\s+)?(?:in\s+)?", between)
    return bool(group) and (" and " in between or "," in between)


_REFERENCE = re.compile(r"\bTable\s+(\d+(?:\s?[:.]\s?\d+)+)")


def _table_pages(texts: dict[int, str]) -> dict[str, set[int]]:
    """Where is which table? Caption "Table 10: 2 ..." at the start of a line, plus the next page."""
    out: dict[str, set[int]] = {}
    for n, t in texts.items():
        for m in re.finditer(r"(?m)^Table\s+(\d+(?:\s?[:.]\s?\d+)+)", t):
            out.setdefault(re.sub(r"\s", "", m.group(1)), set()).update({n, n + 1})
    return out


def _chain(sentence: str, statements: list, i: int) -> list[int]:
    """The other statements linked to statement i by comparisons ("... vs ...", "... group, ... group, and ...")."""
    out = []
    for direction in (-1, 1):
        j = i
        while 0 <= j + direction < len(statements):
            a, b = (statements[j + direction], statements[j]) if direction < 0 else (statements[j], statements[j + direction])
            if b.start() - a.end() > 120 or not _comparison(sentence[a.end():b.start()]):
                break
            j += direction
            out.append(j)
    return out


def _exact(row: _Row, k: int, p: str) -> Optional[int]:
    """Column in which exactly this statement appears."""
    for i, (zk, zp) in enumerate(row.cells):
        if zk == k and _equal(zp, p):
            return i
    return None


def check(texts: dict[int, str]) -> list[Finding]:
    """texts: pages after numcheck.document.prepare (line breaks kept)."""
    rows = [r for n, t in texts.items() for r in _table_rows(n, t)]
    if not rows:
        return []
    everywhere = {(k, float(p)) for r in rows for k, p in r.cells}
    tables = _table_pages(texts)
    how_often: dict[float, int] = {}
    for r in rows:
        for _, zp in r.cells:
            how_often[float(zp)] = how_often.get(float(zp), 0) + 1
    out: list[Finding] = []
    for n, t in texts.items():
        for offset, sentence in _sentences(t):
            if "%" not in sentence or not _running_text(sentence) or _table_like(sentence):
                continue
            statements = [m for m in _STATEMENT.finditer(sentence)
                          if not re.search(r"\bof\W?\s*$", sentence[:m.start()])]   # "vs of 166 [8.4%]": count missing
            values = [(_int(m.group(1)), m.group(3)) for m in statements]
            # rows in which a statement appears exactly; if the sentence names a table, only there
            found = [[r for r in rows if _exact(r, k, p) is not None] for k, p in values]
            named = set().union(*[tables.get(re.sub(r"\s", "", v), set()) for v in _REFERENCE.findall(sentence)]) \
                if _REFERENCE.search(sentence) else set()
            if named:
                found = [[r for r in where if r.page in named] or where for where in found]
            for i, m in enumerate(statements):
                k, p = values[i]
                quote = sentence[max(0, m.start() - 140):m.end() + 40].strip()
                span = (offset + m.start(), offset + m.end())
                if (k, float(p)) in everywhere:
                    out.append(Finding(n, "text_vs_table", quote, f"{k} ({p}%)", f"{k} ({p})", "consistent",
                                       "appears exactly like this in a table", *span))
                    continue
                if float(p) == 0:
                    continue

                def counted_differently(r, zk):
                    # "5 264" read as 264: equal last digits mean a reading error, not a contradiction
                    return (zk != k and k not in r.alternatives and k not in r.sums()
                            and not str(k).endswith(str(zk)) and not str(zk).endswith(str(k)))

                # The neighbours: the statement before and after in the same clause ("58 (5.4%) vs 161 (15.0%)").
                # If a neighbour appears exactly in one row, that is the row of this statement.
                neighbours = []
                for j in (i - 1, i + 1):
                    if not 0 <= j < len(statements):
                        continue
                    lo, hi = sorted((statements[j].end(), m.start())) if j < i else (m.end(), statements[j].start())
                    if hi - lo > 120 or not _comparison(sentence[lo:hi]):
                        continue
                    # If the neighbour appears in several rows (or without decimals), its group
                    # name must confirm the column it is in
                    group = sentence[statements[j].end():statements[j + 1].start() if j + 1 < len(statements) else len(sentence)][:80]
                    if j > i:
                        group = sentence[statements[j].end():][:80]
                    confirmed = [r for r in found[j] if r.header and _column(r, group) == _exact(r, *values[j])]
                    if len(found[j]) == 1 and "." in values[j][1]:
                        neighbours.append((found[j][0], _exact(found[j][0], *values[j])))
                    elif len(confirmed) == 1:
                        neighbours.append((confirmed[0], _exact(confirmed[0], *values[j])))
                neighbour_rows = {id(r): r for r, _ in neighbours}
                one = list(neighbour_rows.values()) if len(neighbour_rows) == 1 else []
                # Comparison over three or more groups: the row in which all other statements of the
                # chain appear is usually only one, even if each alone appears often
                chain = _chain(sentence, statements, i)
                if not one and len(chain) >= 2:
                    common = [r for r in rows if all(_exact(r, *values[j]) is not None for j in chain)
                              and len({_exact(r, *values[j]) for j in chain}) == len(chain)]
                    if len(common) == 1:
                        one = common
                        neighbour_rows = {id(common[0]): common[0]}

                # What the text says about the group: up to the next statement or the end of the clause
                upto = statements[i + 1].start() if i + 1 < len(statements) else len(sentence)
                behind = sentence[m.end():upto].split(";")[0][:80]
                since = statements[i - 1].end() if i > 0 else 0
                ahead = sentence[since:m.start()].split(";")[-1][-80:]

                hits = []
                # 0. Row from the neighbours, column from the group name: the cell must match
                for r in one:
                    col = _column(r, behind) if _column(r, behind) is not None else _column(r, ahead)
                    taken = {c for _, c in neighbours}
                    if col is None or col in taken:
                        continue
                    zk, zp = r.cells[col]
                    # count or percentage must agree, otherwise more likely the row is guessed wrong
                    if (_equal(zp, p) and counted_differently(r, zk)) or (zk == k and not _equal_rounded(zp, p)):
                        hits = [(r, zk, zp, f"column \"{r.header[col]}\"")]
                # 1. Row from the neighbours (or, without a comparison in the sentence, from another
                #    statement of the sentence if the sentence quotes only this one row), cell by
                #    percentage or count
                if not hits:
                    if not one:
                        in_sentence = {id(r): r for j, where in enumerate(found) if j != i for r in where}
                        one = list(in_sentence.values()) if len(in_sentence) == 1 else []
                    hits = [(r, zk, zp, "same percentage, different count") for r in one
                            for zk, zp in r.cells if _equal_exact(zp, p) and counted_differently(r, zk)]
                    # The same count with a different percentage can also be another denominator
                    # (subgroup); without a comparison only for small differences and not too small counts
                    compared = len(neighbour_rows) == 1
                    hits += [(r, zk, zp, "same count, different percentage") for r in one
                             for zk, zp in r.cells if zk == k and not _equal_rounded(zp, p)
                             and (compared and k >= 5 or k >= 20 and abs(float(zp) - float(p)) < 2)
                             and not any(_equal(q, p) for _, q in r.cells)]
                # 2. The row label is in the clause, percentage with decimals
                if not hits and "." in p:
                    words = _content(_clause(sentence, m))
                    hits = [(r, zk, zp, "same percentage, different count") for r in rows
                            if _content(r.label) and _content(r.label) <= words
                            for zk, zp in r.cells if _equal_exact(zp, p) and counted_differently(r, zk)
                            and _close(k, zk)]
                # 3. The percentage occurs only once in all tables, and one word of the row label is in the clause
                if not hits and "." in p and how_often.get(float(p)) == 1:
                    words = _content(_clause(sentence, m))
                    hits = [(r, zk, zp, "same percentage, different count") for r in rows
                            if _partly(_content(r.label), words)
                            for zk, zp in r.cells if _equal_exact(zp, p) and counted_differently(r, zk)
                            and _close(k, zk)]
                if len(hits) != 1:
                    continue
                r, zk, zp, why = hits[0]
                # If the same count appears in the same row with another percentage, the percentage is
                # wrong: it belongs to the neighbouring cell ("1139 (31.4%)", table 1139 (32.3) and 1100 (31.4))
                own = [(yk, yp) for yk, yp in r.cells if yk == k and not _equal_rounded(yp, p)]
                if why.startswith("same percentage") and len(own) == 1:
                    out.append(_finding(n, quote, k, p, r, *own[0],
                                        f"different percentage; {p} % belongs to {zk} in this row", span))
                    continue
                # If the count appears in a row whose label is in the clause, that is the one meant
                words = _content(_clause(sentence, m))
                meant = [(y, yk, yp) for y in rows if _content(y.label) and _content(y.label) <= words
                         for yk, yp in y.cells if yk == k and not _equal_rounded(yp, p)]
                if why.startswith("same percentage") and len(meant) == 1:
                    y, yk, yp = meant[0]
                    out.append(_finding(n, quote, k, p, y, yk, yp,
                                        f"different percentage; {p} % appears in the row \"{r.label[:60]}\"", span))
                    continue
                out.append(_finding(n, quote, k, p, r, zk, zp, why, span))
    return out
