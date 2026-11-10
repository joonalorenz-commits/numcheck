# Tracenum

Find numbers in clinical trial reports that cannot be right, without the data.

A clinical study report or a trial publication prints many numbers that follow
from other numbers in the same document: a percentage from its count and
denominator, a column of categories from the group size, a "Total" column from
the group columns, a p value from a test statistic, a number in the text from
the table it was copied from. numcheck recomputes these and reports the ones
that do not match. It needs only the document (PDF, JATS/PMC XML or text), no
data, no network and no dependencies beyond the Python standard library
(`pypdf` for PDF input).

It is meant as a second pair of eyes for medical writers, reviewers and
meta-researchers, not as a verdict: a flagged number means "cannot be
reproduced from the other numbers on the page", and someone has to look at it.

## Install

```bash
pip install "numcheck[pdf] @ git+https://github.com/joonalorenz-commits/numcheck"
```

Python 3.9 or newer.

## Use

```bash
numcheck report.pdf                     # flagged numbers
numcheck article.xml --all              # also the numbers that are consistent
numcheck *.xml --csv findings.csv       # many documents into one CSV
numcheck report.pdf --json
```

```python
from numcheck import check, document

for f in check(document.read("report.pdf")):
    if f.flagged:
        print(f.page, f.check, f.verdict, f.printed, f.computed, f.note)
```

`check` takes a dict `{page number: text}`, so text from any other source works too.
The exit code is 1 when something is flagged, which makes it usable in a pipeline.

Output for the made-up report in [examples/](examples/synthetic_report.txt) (abridged):

```
synthetic_report.txt: 14 numbers checked, 9 flagged

  page 1 · text_denominator · inconsistent: printed 29.1, computed 29.4
    30/102: the sentence names this denominator, and other statements of the sentence fit it
    "…Of the 102 participants randomized, 30 (29.1%) had a diagnosis of rheumatoid arthritis"

  page 1 · text_denominator · impossible: printed 89.1
    40 (89.1 %): no number of people gives this value when rounded

  page 1 · text_vs_table · inconsistent: printed 165 (15.0%), computed 161 (15.0)
    the table on page 2 shows 161 (15.0) in the row "Incidence of hypoxaemia, n (%)": column "Supine group"

  page 3 · row_total · inconsistent: printed 24, computed 23
    the groups add up to 23, the Total column shows 24 (5 of 6 rows add up)
```

## Checks

| check | what it recomputes |
|---|---|
| `fraction` | "27 of 295 (9.2%)": the percentage from count and denominator |
| `table_cell` | a cell "k (p)" against the N of its column in the table header; other denominators up to the largest N are allowed (subgroups, missing values) |
| `category_sum` | categories whose percentages add up to 100 cannot hold more people than the N of the column |
| `column_partition` | categories whose percentages add up to 100 share one denominator, the sum of their counts; every cell must match it, with or without a header |
| `row_total` | in a table with a "Total (N = …)" column whose N is the sum of the groups, every row must add up |
| `grim_percent` | "82.3% of patients": is the value reachable with any group size named in the document (GRIM, Brown and Heathers 2017) |
| `text_denominator` | "k (p%)" in running text: against the denominator named in the sentence ("Of the 102 participants, …"), against the sum of a list whose percentages add up to 100, or against any whole number at all (GRIM with a count) |
| `text_vs_table` | "k (p%)" in running text against the matching row of a table in the same document |
| `two_group_test` | "27 of 295 … vs 52 of 307 …, P = 0.005": Fisher's exact test, Pearson's chi-square with and without Yates correction |
| `test_statistic` | "t(48) = 2.10, P = 0.04": the p value against t, F, chi-square or z, within the rounding of the statistic (as statcheck, Nuijten et al. 2016) |
| `ci_p` | estimate, 95% CI and p value against each other: estimate outside its interval, interval and significance contradicting each other, p far from the Altman and Bland (2011) approximation |

Verdicts: `impossible` (no whole numbers give the value), `inconsistent` (does
not match the other numbers), `truncated` (only reachable by truncating instead
of rounding) are flagged. `consistent`, `other_denominator`, `other_test`,
`forced_to_100` (percentages adjusted to add up to exactly 100) and `unclear`
(far from an approximation) are not.

Every check is written to stay silent when a number can be read in more than
one way: a row with more cells than the header, a table split over pages, a
count glued to its label, thousands separated by a space, a subgroup named
between a denominator and a percentage. Such numbers are skipped, not guessed.

## Validation

Measured on 475 open access RCT reports from PubMed Central (JAMA Network
Open, BMJ, PLOS Medicine, BMC Medicine, Trials; 2020 to 2025). The scripts are
in [bench/](bench/); `bench/corpus_ids.txt` lists the articles.

**Injected errors.** For every number a check found consistent, the printed
value was changed by one unit of its last digit (52.5 to 52.6, 27 to 28), the
article was checked again, and it was counted whether the change is flagged.
3042 changes, the same for every version of the code:

| check of the changed number | changes | flagged before the three new checks | flagged now |
|---|---:|---:|---:|
| `table_cell` | 2194 | 954 (43%) | 1192 (54%) |
| `fraction` | 605 | 605 (100%) | 605 (100%) |
| `text_vs_table` | 226 | 86 (38%) | 144 (64%) |
| `grim_percent` | 17 | 2 (12%) | 2 (12%) |
| **total** | **3042** | **1647 (54%)** | **1943 (64%)** |

"Before" is `python bench/injected_errors.py --without text_denominator,column_partition,row_total`.
A change is flagged by whichever check notices it, so the new checks also raise
the rates of the older rows.

A one-unit change is the hardest case: many such changes are still consistent
with another reading of the table (a different denominator, a rounded test
statistic), so these rates are a lower bound for that kind of error and say
nothing about other kinds.

**Flags in the unchanged articles.** 157 numbers in 58 of the 475 articles
(before the three new checks: 86 in 34): `table_cell` 48, `column_partition` 41,
`fraction` 29, `text_denominator` 25, `row_total` 5, `text_vs_table` 4,
`two_group_test` 2, `test_statistic`, `grim_percent` and `category_sum` 1 each.
Most are small rounding errors (a percentage off by 0.1); some are counts that
cannot be right.

These flags have been reviewed by the author only. **An independent review is
still missing**; until then, do not read them as a rate of errors in the
literature. If you want to help with that, please open an issue.

To reproduce:

```bash
python bench/pmc_corpus.py --ids        # downloads the 500 articles from NCBI (about 5 minutes)
python bench/injected_errors.py         # about 30 minutes on 16 cores
```

## Limitations

- Text extraction from PDF decides a lot. Tables whose cells come out glued
  together or in a different order are skipped rather than checked.
- Only numbers within one document are compared. An error that is consistent
  everywhere in the document (a wrong number in the data, copied faithfully to
  table and text) is invisible without the data.
- English reports only; the patterns follow the usual CSR and journal styles.
- Thresholds were tuned on the corpus above. Expect false alarms on documents
  that look different, and please report them.

## Related work

- statcheck (Nuijten et al. 2016): p values against test statistics in psychology papers.
- GRIM and GRIMMER (Brown and Heathers 2017; Anaya 2016) and the R package
  [scrutiny](https://github.com/lhdjung/scrutiny) (Jung) for consistency tests of summary statistics.
- INSPECT-SR, a tool for assessing the trustworthiness of randomised controlled trials.
- Altman and Bland (2011), How to obtain the P value from a confidence interval. BMJ 343:d2304.

## License

MIT
