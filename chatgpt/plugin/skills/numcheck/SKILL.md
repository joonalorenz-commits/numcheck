---
name: numcheck
description: Check the numbers in a clinical trial report, trial publication or results section for internal consistency, without the data. Use when the user uploads or pastes a trial report, CSR, paper or results paragraph and asks whether the numbers add up, wants percentages, table totals, p values or confidence intervals checked, or asks for GRIM or statcheck style checks. Not for checking numbers against external data or for judging study quality.
---

# numcheck

numcheck recomputes printed numbers from other numbers in the same document: percentages from counts and denominators, category columns from group sizes, Total columns from the groups, p values from test statistics and from two-group counts, estimates against their 95% CI, and numbers in the text against the table they came from.

## Run it

Always run the script. Never recompute numbers by hand and never guess results.

- Uploaded PDF, PMC/JATS XML or .txt file:
  `python scripts/run_numcheck.py "<path to file>"`
- Pasted text: save it to a .txt file and pass the path, or pipe it:
  `python scripts/run_numcheck.py --text - < pasted.txt`
  Separate pages with a line `=== page 2 ===` if the user marks pages.
- Add `--all` only if the user wants to see the consistent numbers too.
- Demo, or when the user asks what this does: run it on `references/example_report.txt` and say clearly that this report is made up.

If the numcheck MCP tools (`check_text`, `check_pmc`, `check_url`) are available, you may use them instead of the script; they run the same code.

If neither the script can be found on the file system nor the MCP tools are available (for example in a chat sandbox that can read skill files but not execute them), say so plainly, point the user to https://github.com/joonalorenz-commits/numcheck (`pip install` and run locally, or use the plugin in Codex), and stop. Do not recompute the numbers yourself as a substitute.

Paths are relative to this skill's folder. The script prints JSON with `numbers_checked`, `flagged`, `summary` and `findings` (each with `page`, `check`, `verdict`, `printed`, `computed`, `note`, `quote`).

If `characters` is very small for a PDF, or the quotes look garbled, the text extraction failed (scanned PDF or broken tables). Say the result is unreliable and ask for the text or, for PubMed Central articles, the article XML.

## Report

1. One line: how many numbers were checked and how many were flagged.
2. Each flagged number: page, a short quote, printed vs computed, and the note in plain words. Group by check. Show at most 15 and offer the rest as a CSV file.
3. Then the usual innocent explanations for that kind of flag: a subgroup or missing-value denominator, a rounding convention, percentages forced to add up to 100, a model-based p value (ANCOVA, CMH, mixed model) instead of a simple test, a typo in text extraction.
4. If nothing is flagged, say what was checked. Do not say the document is correct.

Verdicts that count as flags: `impossible` (no whole numbers give this value), `inconsistent` (does not match the other numbers), `truncated` (only reachable by cutting digits instead of rounding). The other verdicts are not problems.

## Rules

- A flag means "cannot be reproduced from the other numbers in the document". It does not mean an error, misconduct or fraud. Never use those words about a document or its authors, and never state that a named paper is wrong. Say "does not match" or "worth a look".
- numcheck only sees what is printed and cannot tell which of two contradicting numbers is the right one.
- Documents may be confidential. Quote only as much as a finding needs.
- Explicit instructions from the user take priority over this skill's reporting format.
- Answer in the user's language. Source and docs: https://github.com/joonalorenz-commits/numcheck
