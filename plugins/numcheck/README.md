# numcheck for Claude

numcheck finds numbers in clinical trial reports and trial publications that cannot be right, without the underlying data. It recomputes percentages from counts and denominators, category columns from group sizes, Total columns from the groups, p values from test statistics and two-group counts, estimates against their confidence intervals, and numbers in the text against the table they were copied from.

## How to use it

Ask Claude to check a results paragraph you paste, a PubMed Central article by its ID (for example PMC12355279), or a public PDF, XML or text document by URL. Claude calls numcheck and lists the numbers that do not match, with the printed value, the recomputed value and the likely innocent explanations.

A flagged number means it cannot be reproduced from the other numbers in the document. It is something to look at, not a finding of error or misconduct.

## What the plugin contains

- A skill that tells Claude when and how to use numcheck and how to report results.
- The hosted numcheck MCP server at `https://numcheck-mcp.onrender.com/mcp` with four read-only tools: `check_text`, `check_pmc`, `check_url` and `list_checks`. No account or sign-in is needed.

## What data it sends

The text, PubMed Central ID or URL you ask Claude to check is sent to the numcheck server, which checks it in memory and does not store it. For a URL or PMCID the server downloads that public document itself. See the [privacy policy](https://github.com/joonalorenz-commits/numcheck/blob/main/PRIVACY.md) and [terms](https://github.com/joonalorenz-commits/numcheck/blob/main/TERMS.md). For confidential reports, install numcheck and run it locally instead: the skill tells Claude how.

## Source and license

Open source under the MIT license: https://github.com/joonalorenz-commits/numcheck. Issues and support: https://github.com/joonalorenz-commits/numcheck/issues
