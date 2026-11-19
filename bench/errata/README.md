# Published corrections (errata) of trial papers

`errata_bench.py` collects open-access errata from Europe PMC that contain "should read" / "should have read" and mention a trial, extracts the pairs "<wrong> should read <right>" whose numbers differ, and runs numcheck on the corrected article.

## Result (18 November 2026, numcheck 0.1.0 for the article runs)

- 561 errata found, 47 with at least one numeric "should read" pair, 45 with the article in PMC.
- 93 numeric correction pairs, 128 corrected numbers.
- **Only 1 of 93 pairs (1%) is detectable from the corrected sentence alone**: "150/241 (27.7%)" should read "150/541 (27.7%)". In all other pairs the wrong version is internally consistent (for example "37 (80.4)" for "32 (69.6)" with the same N): the number is wrong, but nothing in the document contradicts it.

## Why there is no detection rate

PubMed Central usually shows the article **after** correction. In the one detectable case, PMC already prints "150/541". The original wording is no longer there to be checked, so a detection rate cannot be measured from PMC. Measuring it needs the originally published PDFs (publisher archives, Wayback Machine), which this script does not fetch.

## What the result means

Journal errata mostly correct numbers that are wrong but consistent: a wrong count copied from another table, a value from an earlier data cut, a transposed row. No check that only has the document can find these. Consistency checks (numcheck) find the minority of errors that contradict other printed numbers; the rest needs the source data or the cited source. The FDA case in `bench/fda_errata/` shows the same split: 4 of about 10 corrected numbers were detectable from the document, and numcheck found all 4.

Re-run with the current code on the same cases: `python bench/errata/errata_bench.py --reevaluate` (fetches once, then uses `out/xml/`).
