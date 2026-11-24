from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation

# What a verdict means. Only FLAGGED verdicts are reported as problems.
VERDICTS = {
    "consistent": "matches the other numbers",
    "other_denominator": "matches with a different denominator than the column N (subgroup, missing values)",
    "other_test": "the p value comes from a model or estimate that cannot be recomputed here",
    "forced_to_100": "percentages adjusted so that they add up to exactly 100",
    "unclear": "far from an approximation; worth a look, not necessarily wrong",
    "truncated": "only reachable by truncating instead of rounding",
    "inconsistent": "does not match the other numbers",
    "impossible": "no combination of whole numbers gives this value",
}
FLAGGED = ("impossible", "inconsistent", "truncated")

# How sure a flag is that a printed number is wrong. Only for flagged findings.
CONFIDENCE = {
    "high": "the numbers that contradict each other are printed together; a reader can verify it in seconds",
    "medium": "depends on how a table was read or on rounding an already rounded value; check the table",
    "low": "a rounding convention or a group size the document does not state; often harmless",
}
# Checks whose result depends on matching cells to columns of a table.
_TABLE_CHECKS = ("table_cell", "category_sum", "column_partition", "row_total", "subgroup_mean")


def _last_digit_off_by_one(printed: str, computed: str) -> bool:
    """0.479 printed, 0.478 computed: the same number apart from the last digit."""
    try:
        p, c = Decimal(printed), Decimal(computed)
    except (InvalidOperation, ValueError):
        return False
    step = Decimal(1).scaleb(p.as_tuple().exponent)
    return abs(p - c) == step


def confidence(check: str, verdict: str, printed: str, computed: str) -> str:
    """'high', 'medium' or 'low' for a flagged finding, '' otherwise.

    The rule is fixed and short on purpose, so that a reviewer can apply it by hand:
    - truncated: low (a rounding convention, not a wrong number)
    - grim_percent: low (the group size is taken from elsewhere in the document)
    - table checks: medium (the match of cells to columns can be wrong)
    - off by one in the last printed digit: medium (rounding of a rounded value)
    - everything else: high
    """
    if verdict not in FLAGGED:
        return ""
    if verdict == "truncated" or check == "grim_percent":
        return "low"
    if check in _TABLE_CHECKS or _last_digit_off_by_one(printed, computed):
        return "medium"
    return "high"


@dataclass
class Finding:
    page: int
    check: str        # see numcheck.CHECKS
    quote: str
    printed: str
    computed: str
    verdict: str      # see VERDICTS
    note: str = ""
    # Position of the printed value in the page text after numcheck.document.prepare
    start: int = -1
    end: int = -1
    # "agrees", "disagrees" or "" (see numcheck.second_reader)
    second_reader: str = ""

    @property
    def flagged(self) -> bool:
        return self.verdict in FLAGGED

    @property
    def confidence(self) -> str:
        level = confidence(self.check, self.verdict, self.printed, self.computed)
        if level and self.second_reader == "disagrees":
            level = {"high": "medium", "medium": "low", "low": "low"}[level]
        return level

    def as_dict(self) -> dict:
        d = asdict(self)
        d["confidence"] = self.confidence
        return d
