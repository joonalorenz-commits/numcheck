from __future__ import annotations

from dataclasses import asdict, dataclass

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

    @property
    def flagged(self) -> bool:
        return self.verdict in FLAGGED

    def as_dict(self) -> dict:
        return asdict(self)
