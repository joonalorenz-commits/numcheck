---
name: numcheck
description: Check the numbers in a clinical trial report, trial publication or results section for internal consistency, without the data. Use when the user pastes or links a trial report, CSR, paper or results paragraph, gives a PubMed Central ID, and asks whether the numbers add up, wants percentages, table totals, p values or confidence intervals checked, or asks for GRIM or statcheck style checks. Not for checking numbers against external data or for judging study quality.
---

# numcheck

numcheck recomputes printed numbers from other numbers in the same document: percentages from counts and denominators, category columns from group sizes, Total columns from the groups, p values from test statistics and two-group counts, estimates against their 95% CI, and numbers in the text against the table they came from.

## Run it

Use the numcheck tools. Never recompute numbers by hand instead and never guess results.

- Pasted text: `check_text` with the text. Separate pages with a line `=== page 2 ===` if the user marks pages.
- PubMed Central article: `check_pmc` with the PMCID.
- Public PDF, JATS XML or text file: `check_url` with the link. For PMC articles, prefer `check_pmc`.
- What is checked and what a verdict means: `list_checks`.
- Set `include_consistent` only if the user wants to see the numbers that matched too.

A local file the user has on disk: if numcheck is installed (`pip install "numcheck[pdf] @ git+https://github.com/joonalorenz-commits/numcheck"`), run `numcheck <file> --json` instead of uploading it anywhere. Confidential documents should stay local.

## Report

1. One line: how many numbers were checked and how many were flagged.
2. Each flagged number: page, a short quote, printed vs computed, and the note in plain words. Group by check. Show at most 15 and offer the rest.
3. Then the usual innocent explanations for that kind of flag: a subgroup or missing-value denominator, a rounding convention, percentages forced to add up to 100, a model-based p value (ANCOVA, CMH, mixed model) instead of a simple test, broken PDF text extraction.
4. If nothing is flagged, say what was checked. Do not say the document is correct.

Flags are the verdicts `impossible`, `inconsistent` and `truncated`. Other verdicts are not problems.

## Rules

- A flag means "cannot be reproduced from the other numbers in the document". It does not mean an error, misconduct or fraud. Never use those words about a document or its authors, and never state that a named paper is wrong.
- Report what numcheck computed. Do not invent corrected values.
- numcheck cannot tell which of two contradicting numbers is right.
- Do not send documents with identifiable patient data to the hosted tools.
- Answer in the user's language.
