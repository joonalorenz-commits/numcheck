# Using numcheck in a validated process

This page is for teams that want to use numcheck as a supporting check in regulated work (medical writing, biostatistics QC, clinical evaluation of medical devices) and need to document that the tool does what it is meant to do. It is not a validation certificate. Validation is always done by the user, for their intended use, in their environment. This page gives the material to do that quickly.

## Intended use

numcheck recomputes numbers in a document from other numbers printed in the same document: a percentage from its count and denominator, a table cell from its column N, a p value from its test statistic, a number in the text from the table it was copied from. With `numcheck-source` it compares a statement with the cited publication in PubMed Central.

It is a **reviewer aid**. It points to numbers a person should look at. It does not decide that a document is wrong and does not replace independent programming, data review or medical review.

Not intended for: checking numbers that need patient-level data, judging whether an analysis method is appropriate, or any automatic decision without a person looking at the flagged passage.

## Risk

A missed error (false negative) leaves the existing review process unchanged: numcheck adds checks, it removes none. A false alarm costs reviewer time. Because of this, numcheck fits a low-risk category for supporting tools (for example GAMP 5 category 3, non-configured, used as published). Users decide the category for their own process.

## Requirements and how they are tested

| Id | Requirement | Evidence |
|---|---|---|
| FR-1..3 | Percentages are recomputed from k/n with exact half-up rounding; truncation is reported separately | `numcheck --selftest` cases FR-1..3, `tests/test_checks.py` |
| TC-1..3 | Table cells are checked against their column N; rows with their own n are read against that n; impossible cells are flagged | selftest TC-1..3, `tests/test_checks.py` |
| TS-1, TG-1 | p values are compared with t/F/chi-square/z statistics and with Fisher's exact test for two proportions | selftest TS-1, TG-1 |
| CF-1 | Every flag has a confidence (high, medium, low) from a fixed, documented rule | `numcheck/finding.py::confidence`, `tests/test_checks.py::test_confidence_levels` |
| SR-1 | With `--second-reader`, every flagged PDF page is read again with a second extraction library; disagreement lowers the confidence and never removes a flag | `numcheck/second_reader.py` |
| SC-1 | `numcheck-source` finds the sentence in the cited source with the same numbers and reports numbers that differ | `tests/test_sources.py` |
| AU-1 | `--audit-log` records version, input SHA-256, options and a hash of all findings for each document; the same input gives the same hashes | `tests/test_selftest.py::test_audit_log_is_reproducible` |

All checks are deterministic: no random numbers, no network access (except `numcheck-source`, which only sends the identifier of the cited article to NCBI/Europe PMC), no language model. The same input and version give the same output.

## Procedure

1. **Installation** (IQ): install a fixed version, for example `pip install "numcheck[pdf2] @ git+https://github.com/joonalorenz-commits/numcheck@<commit>"`. Record the commit.
2. **Operation** (OQ): run `numcheck --selftest`. All cases must pass. Keep the output; it names the version, Python version, platform and a fingerprint of the case set.
3. **Performance** (PQ, optional): run numcheck on a few of your own past documents where you know the errors, and record what it finds. The public benchmarks below show what to expect.
4. **Use**: run with `--audit-log runs.jsonl` and keep the log with the review record. Every flagged number is checked by a person against the document.
5. **Change control**: a new version is a new installation. Repeat steps 1 and 2. Results of the self test and the findings hash show whether anything changed for your documents.

## Measured performance (public, reproducible)

| Benchmark | Result | Where |
|---|---|---|
| 3,042 errors deliberately inserted into 475 open-access RCT papers | 64% detected | `bench/injected_errors.py` |
| 67 public SSCPs of EU medical devices, flags checked by hand | 11 confirmed errors in 7 documents; all 11 are high confidence; after the table fix no false alarm from tables remained | project report (not yet public) |
| FDA briefing document with a published erratum (ODAC 15 March 2024, 19 corrections) | all 4 corrected numbers that are detectable from the document are flagged; the other corrections need the source or the data | `bench/fda_errata/README.md` |
| Published corrections (errata) of 45 trial papers in PMC, 93 numeric corrections | only 1 of 93 corrections was detectable from the sentence itself; the rest were wrong but consistent numbers. A detection rate cannot be measured from PMC, which shows the corrected text | `bench/errata/README.md` |

Known limitations: only numbers whose counterparts are printed in the same document (or the cited open-access source) can be checked, in published papers this is a minority of all numbers; PDF text extraction can misread tables (the second reader and the confidence level make this visible); GRIM-type checks depend on the group size, which is often not printed next to the percentage (these flags are low confidence).

## Versions

- 0.2.0: confidence per flag, second PDF reader, comparison with cited sources (`numcheck-source`), rows with their own n, `--selftest`, `--audit-log`.
- 0.1.0: first public version.
