"""
How many injected errors do the checks find, and how many numbers do they flag in the originals?

    python bench/pmc_corpus.py --ids          # once: the corpus used in the README
    python bench/injected_errors.py [--without text_denominator,column_partition,row_total] [--json]

For every number that a check found consistent in the original article, the
printed value is changed by one unit of its last digit (52.5 -> 52.6,
0.04 -> 0.05, 27 -> 28; in "17 (14.5%)" either the count or the
percentage), the article is checked again, and it is counted whether
something is now flagged at that place (a flagged finding overlapping the
changed value, or a new flagged finding of the same check on the same page).

The places and the changes are fixed in bench/injection_sites.json, so every
version of the code is measured against the same errors. They were drawn from
the checks that existed before the text_denominator, column_partition and
row_total checks were added; `--without` switches checks off to reproduce an
earlier state.

A one-unit change is not always an error a check can see (a p value 0.04 ->
0.05 may still be consistent with a rounded test statistic), so the rate is
a lower bound, and it says nothing about errors of other kinds. Only the
comparison between two states of the code is meaningful.
"""

from __future__ import annotations

import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

import numcheck  # noqa: E402
from numcheck import document  # noqa: E402

CORPUS = HERE / "corpus"
SITES = HERE / "injection_sites.json"
CHECKS_WHEN_FIXED = {"fraction", "table_cell", "category_sum", "grim_percent", "two_group_test",
                     "test_statistic", "ci_p", "text_vs_table"}


def changed(printed: str, rng: random.Random) -> str:
    numbers = list(re.finditer(r"\d+(?:\.\d+)?", printed))
    m = rng.choice(numbers)
    return printed[:m.start()] + _one_unit(m.group(), rng) + printed[m.end():]


def _one_unit(value: str, rng: random.Random) -> str:
    if "." in value:
        places = len(value.split(".")[1])
        step = 10 ** -places
        new = float(value) + (step if rng.random() < 0.5 or float(value) < step * 1.5 else -step)
        return f"{new:.{places}f}"
    n = int(value)
    return str(n + 1 if rng.random() < 0.5 or n == 0 else n - 1)


def usable(pages: dict[int, str]) -> bool:
    return not (len(pages) < 2 and len(pages[1]) < 2000)


def _key(f) -> tuple:
    return (f.page, f.check, f.printed, f.computed, f.verdict)


def fix_sites(paths: list[Path]) -> list[dict]:
    rng = random.Random(1)
    sites = []
    for path in paths:
        pages = document.read(path)
        if not usable(pages):
            continue
        prepared = document.prepare(pages)
        seen = set()
        for f in numcheck.check(pages):
            if f.verdict != "consistent" or f.start < 0 or f.check not in CHECKS_WHEN_FIXED:
                continue
            if (f.page, f.start) in seen or prepared[f.page][f.start:f.end] != f.printed:
                continue
            seen.add((f.page, f.start))
            sites.append({"article": path.stem, "check": f.check, "page": f.page, "start": f.start, "end": f.end,
                          "old": f.printed, "new": changed(f.printed, rng)})
    return sites


def _switch_off(without: list[str]) -> None:
    for name in without:
        module, function = {"text_denominator": ("denominator", "check"), "text_vs_table": ("text_vs_table", "check"),
                            "column_partition": ("checks", "column_partitions"), "row_total": ("checks", "row_totals")}[name]
        setattr(getattr(numcheck, module), function, lambda *a, **k: [])


def _one_article(job: tuple[str, list[dict]]):
    name, sites = job
    pages = document.prepare(document.read(CORPUS / f"{name}.xml"))
    base = numcheck.check(pages)
    original = [f.as_dict() for f in base if f.flagged]
    before = Counter(_key(f) for f in base if f.flagged)
    out = []
    for s in sites:
        text = pages[s["page"]]
        if text[s["start"]:s["end"]] != s["old"]:
            continue
        after = numcheck.check({**pages, s["page"]: text[:s["start"]] + s["new"] + text[s["end"]:]})
        end = s["start"] + len(s["new"])
        hit = any(f.flagged and f.page == s["page"] and f.start < end and f.end > s["start"] for f in after)
        if not hit:
            new_flags = Counter(_key(f) for f in after if f.flagged) - before
            hit = any(k[0] == s["page"] and k[1] == s["check"] for k in new_flags)
        out.append((s, hit))
    return name, original, out


def main(args: list[str]) -> int:
    without: list[str] = []
    if "--without" in args:
        i = args.index("--without")
        without = args[i + 1].split(",")
        args = args[:i] + args[i + 2:]
    _switch_off(without)
    paths = sorted(CORPUS.glob("PMC*.xml"))
    if not paths:
        print("No corpus: run python bench/pmc_corpus.py --ids first")
        return 1
    if SITES.exists():
        sites = json.loads(SITES.read_text())
    else:
        sites = fix_sites(paths)
        SITES.write_text(json.dumps(sites, indent=0), encoding="utf-8")
        print(f"{len(sites)} injection sites fixed in {SITES.name}")
    per_article: dict[str, list[dict]] = defaultdict(list)
    for s in sites:
        per_article[s["article"]].append(s)
    names = [p.stem for p in paths if usable(document.read(p))]
    t0 = time.time()
    injected, found = Counter(), Counter()
    original = []
    with Pool(initializer=_switch_off, initargs=(without,)) as pool:
        for name, orig, results in pool.imap_unordered(_one_article, [(n, per_article.get(n, [])) for n in names]):
            original += [(name, f) for f in orig]
            for s, hit in results:
                injected[s["check"]] += 1
                found[s["check"]] += hit
    print(f"{len(names)} articles, {time.time() - t0:.0f} s" + (f", without {', '.join(without)}" if without else ""))
    print(f"{'check':<16}{'injected':>10}{'flagged':>10}{'rate':>8}")
    for c in sorted(injected, key=lambda c: -injected[c]):
        print(f"{c:<16}{injected[c]:>10}{found[c]:>10}{found[c] / injected[c]:>8.0%}")
    total_i, total_f = sum(injected.values()), sum(found.values())
    print(f"{'total':<16}{total_i:>10}{total_f:>10}{total_f / total_i:>8.0%}")
    print(f"Flagged in the original articles: {len(original)} in {len({n for n, _ in original})} articles")
    for c, k in Counter(f["check"] for _, f in original).most_common():
        print(f"  {c}: {k}")
    if "--json" in args:
        (HERE / "injected_errors.json").write_text(json.dumps({
            "injected": dict(injected), "found": dict(found),
            "original": [{"article": n, **f} for n, f in original]}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
