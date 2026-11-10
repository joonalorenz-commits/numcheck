"""
Exact rounding and the few distributions the checks need, in plain Python.

No numpy or scipy: the package should install anywhere, and every value it
compares against a printed number can be traced to a line in this file.
"""

from __future__ import annotations

import math
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction
from typing import Sequence, Union

Number = Union[Decimal, Fraction, int]


# --- rounding ------------------------------------------------------------

def decimals(printed: str) -> int:
    """Number of decimals shown: "75.6" -> 1, "30" -> 0."""
    return len(printed.split(".")[1]) if "." in printed else 0


def as_decimal(value: Number) -> Decimal:
    if isinstance(value, Fraction):
        with localcontext() as ctx:
            ctx.prec = 40
            return Decimal(value.numerator) / Decimal(value.denominator)
    return Decimal(value)


def round_half_up(value: Number, places: int) -> Decimal:
    """Round half up to the given number of decimals (0.5 goes up)."""
    return as_decimal(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def truncate(value: Number, places: int) -> Decimal:
    return as_decimal(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_DOWN)


def compare_percent(k: int, n: int, printed: str) -> tuple[str, str]:
    """(verdict, computed) for k/n as a percentage against the printed value.

    Verdicts: "consistent", "truncated" (only reachable by truncating instead
    of rounding), "inconsistent".
    """
    if n == 0 or k > n:
        return "inconsistent", "-"
    value = Fraction(100 * k, n)
    places = decimals(printed)
    rounded = round_half_up(value, places)
    if rounded == Decimal(printed):
        return "consistent", str(rounded)
    if truncate(value, places) == Decimal(printed):
        return "truncated", str(rounded)
    return "inconsistent", str(rounded)


# --- exact tests for 2x2 tables -----------------------------------------

def fisher_two_sided(a: int, b: int, c: int, d: int) -> Fraction:
    """Fisher's exact test, two-sided, for the table [[a, b], [c, d]].

    Sums the probability of all tables with the same margins that are at
    most as likely as the observed one (as SAS PROC FREQ does). Integer
    arithmetic, so the comparison needs no tolerance.
    """
    n = a + b + c + d
    row1, col1 = a + b, a + c
    total = math.comb(n, col1)

    def weight(x: int) -> int:
        return math.comb(row1, x) * math.comb(n - row1, col1 - x)

    observed = weight(a)
    lo, hi = max(0, col1 - (n - row1)), min(row1, col1)
    return Fraction(sum(w for w in (weight(x) for x in range(lo, hi + 1)) if w <= observed), total)


def _without_empty(table: Sequence[Sequence[int]]) -> list[list[int]]:
    rows = [list(r) for r in table if sum(r)]
    cols = [j for j in range(len(rows[0])) if any(r[j] for r in rows)] if rows else []
    return [[r[j] for j in cols] for r in rows]


def chi_square(table: Sequence[Sequence[int]]) -> tuple[float, int, float]:
    """Pearson chi-square: (statistic, degrees of freedom, p)."""
    t = _without_empty(table)
    n = sum(map(sum, t))
    rows = [sum(r) for r in t]
    cols = [sum(r[j] for r in t) for j in range(len(t[0]))]
    stat = sum(Fraction((t[i][j] * n - rows[i] * cols[j]) ** 2, rows[i] * cols[j] * n)
               for i in range(len(t)) for j in range(len(t[0])))
    df = (len(t) - 1) * (len(t[0]) - 1)
    return float(stat), df, p_chi_square(float(stat), df)


# --- distributions -------------------------------------------------------

def _gamma_q(a: float, x: float) -> float:
    """Regularized upper incomplete gamma function Q(a, x)."""
    if x <= 0:
        return 1.0
    if x < a + 1:
        total = term = 1.0 / a
        n = a
        for _ in range(10000):
            n += 1
            term *= x / n
            total += term
            if abs(term) < abs(total) * 1e-16:
                break
        return 1.0 - total * math.exp(-x + a * math.log(x) - math.lgamma(a))
    tiny = 1e-300                       # continued fraction (Lentz)
    b = x + 1 - a
    c, d = 1 / tiny, 1 / b
    h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = tiny if abs(d) < tiny else d
        c = b + an / c
        c = tiny if abs(c) < tiny else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-16:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction of the incomplete beta function (modified Lentz)."""
    tiny, qab, qap, qam = 1e-300, a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 1000):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            return h
    raise ArithmeticError("continued fraction does not converge")


def _ibeta(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def p_t_two_sided(t: float, df: float) -> float:
    """P(|T| >= |t|) for Student's t with df degrees of freedom."""
    return _ibeta(df / 2.0, 0.5, df / (df + t * t))


def p_chi_square(statistic: float, df: int) -> float:
    return _gamma_q(df / 2.0, statistic / 2.0)


def p_f(f: float, df1: int, df2: float) -> float:
    """P(F >= f)."""
    if f <= 0:
        return 1.0
    return _ibeta(df2 / 2.0, df1 / 2.0, df2 / (df2 + df1 * f))
