"""
Denominator in the sentence: does "k (p%)" in running text fit the group it refers to?

In text the denominator rarely stands next to the statement, but often in the same sentence:

- explicitly: "Of the 102 participants, 37 (36.3%) had ..." or
  "This study included 275 adults, ... and 175 (63.6%) were female."
- hidden in a list: "264 (62.3%) were female and 160 (37.7%) were male".
  The percentages add up to 100, so the denominator is the sum of the counts
  (424), and every statement must fit it.
- not at all, and still checkable: for "41 (89.1%)" there is no whole number
  of people at all that gives 89.1 % when rounded (GRIM with a count,
  Brown & Heathers 2017).

Statements "k/n (p%)" and "k of n (p%)" are checked by checks.fractions.
Reported is only what no reading can save: an explicit denominator only when
no subgroup stands in between ("of whom", "of these") and another statement
of the sentence or proximity confirms it; a list only when the percentages
add up to exactly 100 up to rounding and at most a third of the statements
do not fit.
"""

from __future__ import annotations

import math
import re
from fractions import Fraction
from typing import Optional

from numcheck.checks import NUMBER
from numcheck.finding import Finding
from numcheck.stats import compare_percent, decimals

_WHOLE = r"\d{1,3}(?:[, ]\d{3})+(?![\d.])|\d+"
# "37 (36.3%)", "42 participants (5.3%)", "45 users (97.8%)", not "37/102 (36.3%)".
# One word between count and bracket, but no unit ("29 years (43.9%)" is an age).
_UNIT = (r"years?|months?|weeks?|days?|hours?|minutes?|mg|kg|g|ml|cm|mm|points?|times|sessions|visits|items|doses"
         r"|included|scored|reported|had|were|was")
_STATEMENT = re.compile(rf"(?<![\d.,/−<>≤≥-])(?<!\d )({_WHOLE})(?!\s?(?:/|of|out of)\s?\d)((?: (?!(?:{_UNIT})\b)[a-z]+)?)"
                        rf"\s?[(\[]\s?({NUMBER})\s?%\s?[)\]]")
# A range or an age before it: "between 35 and 49 (48.2%)", "aged 18 to 29 (43.9%)"
_NO_COUNT = re.compile(r"(?:\bbetween \d+\s?(?:and|to)|\bages? (?:of )?\d+\s?(?:and|to|-|–)|\d\s?(?:to|-|–)|\bages?(?: of)?"
                       r"|\baged|\bof(?: the| all)?\W?)\s*$")
# A group or its own denominator after it: "49 (98%) in the active group", "1174 (68.2%) of 1721"
_OWN_GROUP = re.compile(r"^\s*(?:\w+\s)?(?:were\s|was\s)?(?:(?:in|on|for) the [\w\s\-+/.]{1,40}?(?:group|arm|cohort)|of \d)")
_PEOPLE = (r"participants?|patients?|adults|children|women|men|individuals|respondents|users|subjects|people|persons"
           r"|infants|neonates|students|mothers|caregivers|residents|veterans|survivors|smokers|pregnancies|cases")
# "Of the 102 participants", "Among 1,203 adults", "included 275 adults", "In total, 593 patients"
_DENOMINATOR = re.compile(rf"(?<![\d.,])({_WHOLE})(?: [a-zA-Z\-]+){{0,2}}? (?:{_PEOPLE})\b(?!\s?[(\[]\s?{NUMBER}\s?%)")
# A subgroup between denominator and statement: then the denominator is another one
_SUBGROUP = re.compile(r"\b(?:of|among|in) (?:these|them|whom|those|which)\b|\bwho\b|\bwith (?:complete|available)|"
                       r"\bsubgroup|\bresponded|\bcompleted|\bremaining|\bexcluding|\bexcept|\bof the\b|\bamong the\b|"
                       r"\bin the [a-z\- ]+ (?:group|arm)\b|;", re.I)


def _int(x: str) -> int:
    return int(re.sub(r"[, ]", "", x))


def reachable(k: int, p: str) -> Optional[tuple[str, int]]:
    """Is there a whole number n >= k for which k/n gives p when rounded, or at least when truncated?"""
    value = Fraction(p)
    if value > 100:
        return None
    if k == 0:
        return ("consistent", 1) if value == 0 else None
    if value == 0:
        return None
    unit = Fraction(1, 10 ** decimals(p))
    # Rounded: 100k/n in [p - 1/2, p + 1/2), so n in (100k/(p + 1/2), 100k/(p - 1/2)]. A whole number in
    # this range lies, if at all, right at its lower end, so a few candidates are enough.
    for top, bottom, verdict in ((value + unit / 2, value - unit / 2, "consistent"), (value + unit, value, "truncated")):
        low = max(k, math.floor(100 * k / top))
        for n in range(low, low + 4):
            if bottom > 0 and n > 100 * k / bottom:
                break
            if compare_percent(k, n, p)[0] == verdict:
                return (verdict, n)
    return None


def _running_text(sentence: str) -> bool:
    return len(re.findall(r"\b[a-z]{3,}\b", sentence)) >= 6


def _table_like(sentence: str) -> bool:
    return len(re.findall(rf"\(\s?{NUMBER}\s?%?\s?\)\s?\d", sentence)) >= 2


def _sentences(t: str):
    start = 0
    for m in re.finditer(r"(?<=[a-z)%\]])\.\s+(?=[A-Z])|\n", t):
        yield start, t[start:m.start() + 1]
        start = m.end()
    yield start, t[start:]


def _explicit(sentence: str, m: re.Match) -> Optional[tuple[int, int]]:
    """The nearest denominator before the statement in the same sentence, and its distance; no subgroup in between."""
    candidates = [x for x in _DENOMINATOR.finditer(sentence[:m.start()]) if not _STATEMENT.match(sentence, x.start())]
    if not candidates:
        return None
    x = candidates[-1]
    between = sentence[x.end():m.start()]
    if _SUBGROUP.search(between) or re.search(r"\d+\s?/\s?\d+|\bof \d", between):
        return None
    # Another number of people in between ("343 screened, 240 were randomized and 169 (70.4%)")
    k = _int(m.group(1))
    if any(int(z) >= k for z in re.findall(r"(?<![\d.,\[(])\d+(?![\d.,%\]])", between)):
        return None
    if _OWN_GROUP.match(sentence[m.end():]):
        return None
    return _int(x.group(1)), m.start() - x.end()


def _finding(page, sentence, offset, m, n, why) -> Finding:
    k, p = _int(m.group(1)), m.group(3)
    verdict, computed = compare_percent(k, n, p)
    return Finding(page, "text_denominator", sentence[max(0, m.start() - 140):m.end() + 40].strip(), p, computed,
                   verdict, f"{k}/{n}: {why}", offset + m.start(3), offset + m.end(3))


def check(texts: dict[int, str]) -> list[Finding]:
    """texts: pages after numcheck.document.prepare."""
    out: list[Finding] = []
    for page, t in sorted(texts.items()):
        for offset, sentence in _sentences(t):
            if "%" not in sentence or not _running_text(sentence) or _table_like(sentence):
                continue
            statements = [m for m in _STATEMENT.finditer(sentence) if not _NO_COUNT.search(sentence[:m.start()])]
            if not statements:
                continue
            reported: set[int] = set()

            # 1. GRIM with a count: no number of people gives this value
            for i, m in enumerate(statements):
                k, p = _int(m.group(1)), m.group(3)
                if "." not in p:
                    continue
                possible = reachable(k, p)
                if possible is None or possible[0] == "truncated":
                    verdict = "impossible" if possible is None else "truncated"
                    note = (f"{k} ({p} %): no number of people gives this value when rounded"
                            + ("" if possible is None else f", truncated with {possible[1]}"))
                    out.append(Finding(page, "text_denominator", sentence[max(0, m.start() - 140):m.end() + 40].strip(),
                                       p, "-" if possible is None else f"{k}/{possible[1]}", verdict, note,
                                       offset + m.start(3), offset + m.end(3)))
                    reported.add(i)

            # 2. A list: percentages add up to 100, denominator = sum of the counts
            values = [(_int(m.group(1)), m.group(3)) for m in statements]
            for a in range(len(statements)):
                for b in range(len(statements), a + 1, -1):
                    run = values[a:b]
                    # whole percentages add up to 100 by chance too easily
                    if b - a < 2 or decimals(run[0][1]) == 0 or any(decimals(p) != decimals(run[0][1]) for _, p in run):
                        continue
                    if any(";" in sentence[statements[j].end():statements[j + 1].start()] for j in range(a, b - 1)):
                        continue
                    if any(sentence[statements[j].end():statements[j + 1].start()].count(" ") > 12 for j in range(a, b - 1)):
                        continue
                    total = sum(Fraction(p) for _, p in run)
                    tolerance = Fraction(b - a, 2 * 10 ** decimals(run[0][1]))
                    if abs(total - 100) > tolerance or total == 0:
                        continue
                    n = sum(k for k, _ in run)
                    wrong = [a + j for j, (k, p) in enumerate(run) if compare_percent(k, n, p)[0] != "consistent"]
                    if 0 < len(wrong) <= max(1, (b - a) // 3):
                        for j in wrong:
                            if j not in reported:
                                out.append(_finding(page, sentence, offset, statements[j], n,
                                                    f"the percentages of the list add up to 100, the counts to {n}"))
                                reported.add(j)
                    for j in range(a, b):
                        if j not in wrong and j not in reported:
                            out.append(_finding(page, sentence, offset, statements[j], n, "list adds up to 100 %"))
                            reported.add(j)
                    break

            # 3. An explicit denominator in the sentence
            for i, m in enumerate(statements):
                if i in reported:
                    continue
                found = _explicit(sentence, m)
                if not found:
                    continue
                n, distance = found
                k, p = values[i]
                if k > n:
                    continue
                if compare_percent(k, n, p)[0] == "consistent":
                    out.append(_finding(page, sentence, offset, m, n, "denominator named in the sentence"))
                    continue
                # Does another statement of the sentence confirm this denominator, or is it right before it?
                others = [j for j, (kk, pp) in enumerate(values) if j != i and kk <= n
                          and compare_percent(kk, n, pp)[0] == "consistent"]
                statements_between = any(m.start() - distance < s < m.start() for s in (x.start() for x in statements))
                later = [j for j in range(len(statements)) if j != i and _explicit(sentence, statements[j])
                         and _explicit(sentence, statements[j])[0] == n]
                if later and not others:
                    continue                  # no other statement fits n: n is not their denominator
                if others or (distance <= 40 and not statements_between):
                    out.append(_finding(page, sentence, offset, m, n, "the sentence names this denominator"
                                        + (", and other statements of the sentence fit it" if others else "")))
    return out
